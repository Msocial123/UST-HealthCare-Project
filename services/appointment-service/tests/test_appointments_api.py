import uuid

import pytest
from sqlalchemy import select

from app.models.outbox_event import OutboxEvent
from tests.conftest import at, booking_payload

URL = "/api/v1/appointments"


def _outbox(app) -> list[OutboxEvent]:
    with app.state.session_factory() as session:
        return list(session.scalars(select(OutboxEvent).order_by(OutboxEvent.occurred_at)).all())


# Booking ------------------------------------------------------------------------------------------


def test_book_appointment(client, auth, provider_id) -> None:
    payload = booking_payload(
        provider_id, starts_at="2030-03-04T10:00:00+01:00", ends_at="2030-03-04T10:30:00+01:00"
    )
    response = client.post(URL, json=payload, headers=auth("RECEPTIONIST"))
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["status"] == "BOOKED"
    assert body["version"] == 1
    assert body["reason_code"] == "FOLLOW_UP"
    assert body["starts_at"].startswith("2030-03-04T09:00:00")  # normalised to UTC
    assert body["cancellation_reason"] is None
    assert uuid.UUID(body["created_by"])


def test_overlapping_booking_for_same_provider_is_409(client, admin, book, provider_id) -> None:
    book(provider_id, starts_at=at(4, 9), ends_at=at(4, 10))
    for starts, ends in [(at(4, 9), at(4, 10)), (at(4, 9, 30), at(4, 10, 30)), (at(4, 8, 30), at(4, 9, 15))]:
        response = client.post(
            URL, json=booking_payload(provider_id, starts_at=starts, ends_at=ends), headers=admin
        )
        assert response.status_code == 409
        assert response.json()["error"]["code"] == "conflict"


def test_adjacent_and_other_provider_bookings_are_allowed(book, provider_id) -> None:
    book(provider_id, starts_at=at(4, 9), ends_at=at(4, 10))
    book(provider_id, starts_at=at(4, 10), ends_at=at(4, 10, 30))
    book(provider_id, starts_at=at(4, 8, 30), ends_at=at(4, 9))
    book(str(uuid.uuid4()), starts_at=at(4, 9), ends_at=at(4, 10))


@pytest.mark.parametrize(
    "overrides",
    [
        {"starts_at": at(4, 10), "ends_at": at(4, 9)},
        {"starts_at": at(4, 10), "ends_at": at(4, 10)},
        {"starts_at": at(4, 10), "ends_at": at(4, 10, 2)},
        {"starts_at": at(4, 8), "ends_at": at(4, 17)},
        {"starts_at": "2030-03-04T09:00:00", "ends_at": "2030-03-04T09:30:00"},
        {"reason_code": "Patient has chest pain"},
        {"patient_id": "not-a-uuid"},
        {"unexpected": "field"},
    ],
    ids=[
        "end-before-start",
        "zero-length",
        "too-short",
        "too-long",
        "naive",
        "free-text-reason",
        "bad-id",
        "extra",
    ],
)
def test_invalid_booking_is_422(client, admin, provider_id, overrides) -> None:
    response = client.post(URL, json=booking_payload(provider_id, **overrides), headers=admin)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"
    assert "chest pain" not in response.text


def test_booking_in_the_past_is_422(client, admin, provider_id) -> None:
    payload = booking_payload(provider_id, starts_at="2030-01-15T07:00:00Z", ends_at="2030-01-15T07:30:00Z")
    response = client.post(URL, json=payload, headers=admin)
    assert response.status_code == 422
    assert response.json()["error"]["message"] == "starts_at must be in the future"


# Read / search ------------------------------------------------------------------------------------


def test_get_appointment(client, auth, book, provider_id) -> None:
    created = book(provider_id)
    for role in ("ADMIN", "RECEPTIONIST", "DOCTOR"):
        response = client.get(f"{URL}/{created['id']}", headers=auth(role))
        assert response.status_code == 200
        assert response.json() == created


def test_unknown_appointment_is_404(client, admin) -> None:
    unknown = uuid.uuid4()
    assert client.get(f"{URL}/{unknown}", headers=admin).json()["error"]["code"] == "not_found"
    for action, body in [
        ("reschedule", {"starts_at": at(5, 9), "ends_at": at(5, 10), "version": 1}),
        ("cancel", {"cancellation_reason": "PATIENT_REQUEST"}),
        ("check-in", None),
        ("complete", None),
        ("no-show", None),
    ]:
        response = client.post(f"{URL}/{unknown}/{action}", json=body, headers=admin)
        assert response.status_code == 404, action


def test_search_filters_and_pagination(client, auth, book, provider_id) -> None:
    patient = str(uuid.uuid4())
    first = book(provider_id, patient_id=patient, starts_at=at(4, 9), ends_at=at(4, 9, 30))
    second = book(provider_id, starts_at=at(5, 9), ends_at=at(5, 9, 30))
    other = book(str(uuid.uuid4()), patient_id=patient, starts_at=at(6, 9), ends_at=at(6, 9, 30))
    client.post(
        f"{URL}/{second['id']}/cancel", json={"cancellation_reason": "PATIENT_REQUEST"}, headers=auth()
    )
    headers = auth("DOCTOR")

    def ids(**params) -> list[str]:
        response = client.get(URL, params=params, headers=headers)
        assert response.status_code == 200, response.text
        return [item["id"] for item in response.json()["items"]]

    assert ids() == [first["id"], second["id"], other["id"]]
    assert ids(provider_id=provider_id) == [first["id"], second["id"]]
    assert ids(patient_id=patient) == [first["id"], other["id"]]
    assert ids(status="CANCELLED") == [second["id"]]
    assert ids(date_from=at(5, 0), date_to=at(6, 0)) == [second["id"]]
    assert ids(facility_id=other["facility_id"]) == [other["id"]]
    page = client.get(URL, params={"limit": 2, "offset": 1}, headers=headers).json()
    assert page["total"] == 3 and page["limit"] == 2 and page["offset"] == 1
    assert [item["id"] for item in page["items"]] == [second["id"], other["id"]]


@pytest.mark.parametrize(
    "params",
    [
        {"limit": 0},
        {"limit": 101},
        {"offset": -1},
        {"status": "UNKNOWN"},
        {"date_from": "2030-03-04T00:00:00"},
        {"date_from": at(5, 0), "date_to": at(4, 0)},
    ],
)
def test_invalid_search_is_422(client, admin, params) -> None:
    response = client.get(URL, params=params, headers=admin)
    assert response.status_code == 422


# Reschedule ---------------------------------------------------------------------------------------


def test_reschedule(client, admin, book, provider_id) -> None:
    created = book(provider_id, starts_at=at(4, 9), ends_at=at(4, 9, 30))
    body = {"starts_at": at(4, 9, 15), "ends_at": at(4, 9, 45), "version": 1}  # overlaps only itself
    response = client.post(f"{URL}/{created['id']}/reschedule", json=body, headers=admin)
    assert response.status_code == 200, response.text
    moved = response.json()
    assert moved["starts_at"].startswith("2030-03-04T09:15:00") and moved["version"] == 2
    # The old time is free again.
    client.post(
        URL, json=booking_payload(provider_id, starts_at=at(4, 9), ends_at=at(4, 9, 15)), headers=admin
    )


def test_reschedule_onto_busy_slot_is_409(client, admin, book, provider_id) -> None:
    book(provider_id, starts_at=at(4, 10), ends_at=at(4, 11))
    created = book(provider_id, starts_at=at(4, 9), ends_at=at(4, 9, 30))
    body = {"starts_at": at(4, 10, 30), "ends_at": at(4, 11, 30), "version": 1}
    response = client.post(f"{URL}/{created['id']}/reschedule", json=body, headers=admin)
    assert response.status_code == 409
    assert client.get(f"{URL}/{created['id']}", headers=admin).json()["version"] == 1


def test_reschedule_with_stale_version_is_409(client, admin, book, provider_id) -> None:
    created = book(provider_id)
    first = {"starts_at": at(5, 9), "ends_at": at(5, 9, 30), "version": 1}
    assert client.post(f"{URL}/{created['id']}/reschedule", json=first, headers=admin).status_code == 200
    stale = {"starts_at": at(6, 9), "ends_at": at(6, 9, 30), "version": 1}
    response = client.post(f"{URL}/{created['id']}/reschedule", json=stale, headers=admin)
    assert response.status_code == 409
    assert response.json()["error"]["details"] == {"current_version": 2}


@pytest.mark.parametrize(
    "body",
    [
        {"starts_at": at(5, 10), "ends_at": at(5, 9), "version": 1},
        {"starts_at": at(5, 9), "ends_at": at(5, 10)},
        {"starts_at": "2030-01-01T09:00:00Z", "ends_at": "2030-01-01T09:30:00Z", "version": 1},
    ],
    ids=["end-before-start", "missing-version", "in-the-past"],
)
def test_invalid_reschedule_is_422(client, admin, book, provider_id, body) -> None:
    created = book(provider_id)
    assert client.post(f"{URL}/{created['id']}/reschedule", json=body, headers=admin).status_code == 422


def test_reschedule_cancelled_appointment_is_409(client, admin, book, provider_id) -> None:
    created = book(provider_id)
    client.post(
        f"{URL}/{created['id']}/cancel", json={"cancellation_reason": "PATIENT_REQUEST"}, headers=admin
    )
    body = {"starts_at": at(5, 9), "ends_at": at(5, 9, 30), "version": 2}
    assert client.post(f"{URL}/{created['id']}/reschedule", json=body, headers=admin).status_code == 409


# Cancel and status transitions --------------------------------------------------------------------


def test_cancel_frees_the_slot(client, auth, book, provider_id) -> None:
    created = book(provider_id)
    response = client.post(
        f"{URL}/{created['id']}/cancel",
        json={"cancellation_reason": "patient_request", "version": 1},
        headers=auth("RECEPTIONIST"),
    )
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "CANCELLED"
    assert response.json()["cancellation_reason"] == "PATIENT_REQUEST"
    book(provider_id)  # same slot is bookable again


def test_cancel_with_stale_version_or_bad_reason(client, admin, book, provider_id) -> None:
    created = book(provider_id)
    stale = client.post(
        f"{URL}/{created['id']}/cancel", json={"cancellation_reason": "X_Y", "version": 9}, headers=admin
    )
    assert stale.status_code == 409
    missing = client.post(f"{URL}/{created['id']}/cancel", json={}, headers=admin)
    assert missing.status_code == 422


def test_check_in_then_complete(client, auth, book, provider_id) -> None:
    created = book(provider_id)
    checked_in = client.post(f"{URL}/{created['id']}/check-in", headers=auth("RECEPTIONIST"))
    assert checked_in.status_code == 200 and checked_in.json()["status"] == "CHECKED_IN"
    completed = client.post(f"{URL}/{created['id']}/complete", json={"version": 2}, headers=auth("DOCTOR"))
    assert completed.status_code == 200 and completed.json()["status"] == "COMPLETED"
    assert completed.json()["version"] == 3


def test_no_show_frees_the_slot(client, auth, book, provider_id) -> None:
    created = book(provider_id)
    response = client.post(f"{URL}/{created['id']}/no-show", json={}, headers=auth("DOCTOR"))
    assert response.status_code == 200 and response.json()["status"] == "NO_SHOW"
    book(provider_id)


def test_completed_appointment_still_occupies_the_slot(client, admin, book, provider_id) -> None:
    created = book(provider_id)
    client.post(f"{URL}/{created['id']}/check-in", headers=admin)
    client.post(f"{URL}/{created['id']}/complete", headers=admin)
    assert client.post(URL, json=booking_payload(provider_id), headers=admin).status_code == 409


@pytest.mark.parametrize(
    ("setup", "action"),
    [
        ([], "complete"),
        (["check-in"], "check-in"),
        (["check-in"], "no-show"),
        (["check-in"], "cancel"),
        (["check-in", "complete"], "cancel"),
        (["no-show"], "check-in"),
        (["cancel"], "cancel"),
        (["cancel"], "check-in"),
    ],
)
def test_invalid_status_transition_is_409(client, admin, book, provider_id, setup, action) -> None:
    created = book(provider_id)
    reason = {"cancellation_reason": "PATIENT_REQUEST"}
    for step in setup:
        body = reason if step == "cancel" else None
        assert client.post(f"{URL}/{created['id']}/{step}", json=body, headers=admin).status_code == 200
    body = reason if action == "cancel" else None
    response = client.post(f"{URL}/{created['id']}/{action}", json=body, headers=admin)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "conflict"


def test_transition_with_stale_version_is_409(client, admin, book, provider_id) -> None:
    created = book(provider_id)
    assert (
        client.post(f"{URL}/{created['id']}/check-in", json={"version": 5}, headers=admin).status_code == 409
    )


# Outbox -------------------------------------------------------------------------------------------


def test_outbox_events_are_written_with_each_change(app, client, admin, book, provider_id) -> None:
    created = book(provider_id)
    body = {"starts_at": at(5, 9), "ends_at": at(5, 9, 30), "version": 1}
    client.post(f"{URL}/{created['id']}/reschedule", json=body, headers=admin)
    client.post(
        f"{URL}/{created['id']}/cancel", json={"cancellation_reason": "PATIENT_REQUEST"}, headers=admin
    )

    events = _outbox(app)
    assert [event.event_type for event in events] == [
        "AppointmentCreated",
        "AppointmentRescheduled",
        "AppointmentCancelled",
    ]
    assert all(str(event.aggregate_id) == created["id"] and event.published_at is None for event in events)
    assert [event.payload["version"] for event in events] == [1, 2, 3]
    assert events[1].payload["starts_at"].startswith("2030-03-05T09:00:00")
    # Payloads carry IDs, times and status only: no reason codes or other details.
    assert set(events[0].payload) == {
        "event_type", "appointment_id", "patient_id", "provider_id", "facility_id",
        "starts_at", "ends_at", "status", "version", "occurred_at",
    }  # fmt: skip
    assert "FOLLOW_UP" not in str([event.payload for event in events])


def test_status_transitions_do_not_emit_events(app, client, admin, book, provider_id) -> None:
    created = book(provider_id)
    client.post(f"{URL}/{created['id']}/check-in", headers=admin)
    assert [event.event_type for event in _outbox(app)] == ["AppointmentCreated"]


def test_outbox_failure_rolls_back_the_booking(app, admin, provider_id, monkeypatch) -> None:
    from fastapi.testclient import TestClient

    from app.repositories.appointment_repository import AppointmentRepository

    def broken_add_event(self, outbox_event):
        raise RuntimeError("simulated outbox failure")

    monkeypatch.setattr(AppointmentRepository, "add_event", broken_add_event)
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.post(URL, json=booking_payload(provider_id), headers=admin)
        assert response.status_code == 500
        assert client.get(URL, headers=admin).json()["total"] == 0  # appointment was not committed
        assert _outbox(app) == []


def test_conflicting_booking_writes_no_outbox_event(app, client, admin, book, provider_id) -> None:
    book(provider_id)
    assert client.post(URL, json=booking_payload(provider_id), headers=admin).status_code == 409
    assert len(_outbox(app)) == 1
