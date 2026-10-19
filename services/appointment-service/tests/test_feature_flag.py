"""Rollback layer 1: APPOINTMENTS_ENABLED=false stops book/reschedule/cancel; reads keep working."""

import pytest

from tests.conftest import at, booking_payload

DISABLED = {"error": {"code": "feature_disabled", "message": "Appointment booking is currently disabled"}}


@pytest.fixture
def created(book, provider_id) -> dict:
    return book(provider_id)


@pytest.fixture
def flag_off(app, created) -> dict:
    app.state.settings.appointments_enabled = False
    return created


def test_flag_off_returns_documented_error_for_book_reschedule_cancel(client, admin, flag_off, provider_id):
    calls = [
        ("/api/v1/appointments", booking_payload(provider_id, starts_at=at(9, 9), ends_at=at(9, 10))),
        (
            f"/api/v1/appointments/{flag_off['id']}/reschedule",
            {"starts_at": at(9, 9), "ends_at": at(9, 10), "version": 1},
        ),
        (f"/api/v1/appointments/{flag_off['id']}/cancel", {"cancellation_reason": "PATIENT_REQUEST"}),
    ]
    for url, body in calls:
        response = client.post(url, json=body, headers=admin)
        assert response.status_code == 503, url
        assert response.json() == DISABLED
    # Nothing changed while the flag was off.
    current = client.get(f"/api/v1/appointments/{flag_off['id']}", headers=admin).json()
    assert current == flag_off
    assert client.get("/api/v1/appointments", headers=admin).json()["total"] == 1


def test_flag_off_keeps_reads_and_status_transitions_working(client, auth, flag_off) -> None:
    assert client.get(f"/api/v1/appointments/{flag_off['id']}", headers=auth("DOCTOR")).status_code == 200
    assert client.get("/api/v1/appointments", headers=auth("RECEPTIONIST")).status_code == 200
    response = client.post(f"/api/v1/appointments/{flag_off['id']}/check-in", headers=auth("RECEPTIONIST"))
    assert response.status_code == 200 and response.json()["status"] == "CHECKED_IN"


def test_authentication_and_authorization_run_before_the_flag(client, auth, flag_off, provider_id) -> None:
    assert client.post("/api/v1/appointments", json=booking_payload(provider_id)).status_code == 401
    response = client.post("/api/v1/appointments", json=booking_payload(provider_id), headers=auth("DOCTOR"))
    assert response.status_code == 403


def test_flag_back_on_restores_booking(app, client, admin, flag_off, provider_id) -> None:
    app.state.settings.appointments_enabled = True
    body = booking_payload(provider_id, starts_at=at(9, 9), ends_at=at(9, 10))
    assert client.post("/api/v1/appointments", json=body, headers=admin).status_code == 201
