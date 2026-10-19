"""Booking integrity under concurrency. Requires PostgreSQL: set TEST_DATABASE_URL (skipped on SQLite)."""

import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime

import pytest
from sqlalchemy import insert, select
from sqlalchemy.exc import IntegrityError

from app.models.appointment import PROVIDER_OVERLAP_CONSTRAINT, Appointment
from app.models.outbox_event import OutboxEvent
from app.repositories.appointment_repository import AppointmentRepository
from tests.conftest import IS_POSTGRESQL, at, booking_payload

pytestmark = pytest.mark.skipif(not IS_POSTGRESQL, reason="needs PostgreSQL via TEST_DATABASE_URL")
URL = "/api/v1/appointments"


def _race(client, admin, bodies) -> list[int]:
    with ThreadPoolExecutor(max_workers=len(bodies)) as pool:
        futures = [pool.submit(client.post, URL, json=body, headers=admin) for body in bodies]
        return sorted(future.result().status_code for future in futures)


def test_simultaneous_bookings_for_same_slot_one_wins(client, admin, provider_id) -> None:
    for attempt in range(5):
        start, end = at(10 + attempt, 9), at(10 + attempt, 9, 30)
        bodies = [booking_payload(provider_id, starts_at=start, ends_at=end) for _ in range(2)]
        assert _race(client, admin, bodies) == [201, 409]


def test_exclusion_constraint_is_final_authority_when_precheck_is_bypassed(
    app, client, admin, provider_id, monkeypatch
) -> None:
    """Both requests pass the application pre-check at the same moment; only the database can stop one."""
    barrier = threading.Barrier(2, timeout=10)

    def racing_precheck(self, *args, **kwargs):
        barrier.wait()
        return None

    monkeypatch.setattr(AppointmentRepository, "find_overlapping", racing_precheck)
    bodies = [
        booking_payload(provider_id, starts_at=at(20, 9), ends_at=at(20, 10)),
        booking_payload(provider_id, starts_at=at(20, 9, 30), ends_at=at(20, 10, 30)),
    ]
    assert _race(client, admin, bodies) == [201, 409]
    with app.state.session_factory() as session:
        assert len(session.scalars(select(Appointment)).all()) == 1
        assert len(session.scalars(select(OutboxEvent)).all()) == 1  # loser's event was rolled back


def test_reschedule_race_is_rejected_by_constraint(
    app, client, admin, book, provider_id, monkeypatch
) -> None:
    first = book(provider_id, starts_at=at(21, 9), ends_at=at(21, 10))
    monkeypatch.setattr(AppointmentRepository, "find_overlapping", lambda self, *a, **k: None)
    response = client.post(
        URL, json=booking_payload(provider_id, starts_at=at(21, 9), ends_at=at(21, 10)), headers=admin
    )
    assert response.status_code == 409
    second = book(provider_id, starts_at=at(21, 11), ends_at=at(21, 12))
    body = {"starts_at": at(21, 9, 30), "ends_at": at(21, 10, 30), "version": 1}
    assert client.post(f"{URL}/{second['id']}/reschedule", json=body, headers=admin).status_code == 409
    assert client.get(f"{URL}/{first['id']}", headers=admin).json()["status"] == "BOOKED"


def test_concurrent_cancels_with_same_version_one_wins(client, admin, book, provider_id, monkeypatch) -> None:
    created = book(provider_id, starts_at=at(22, 9), ends_at=at(22, 10))
    barrier = threading.Barrier(2, timeout=10)
    original_get = AppointmentRepository.get

    def racing_get(self, appointment_id):
        appointment = original_get(self, appointment_id)
        barrier.wait()
        return appointment

    monkeypatch.setattr(AppointmentRepository, "get", racing_get)
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [
            pool.submit(
                client.post,
                f"{URL}/{created['id']}/cancel",
                json={"cancellation_reason": "PATIENT_REQUEST", "version": 1},
                headers=admin,
            )
            for _ in range(2)
        ]
        assert sorted(future.result().status_code for future in futures) == [200, 409]


def _row(provider_id: uuid.UUID, start_hour: int, status: str) -> dict:
    return {
        "id": uuid.uuid4(),
        "patient_id": uuid.uuid4(),
        "provider_id": provider_id,
        "facility_id": uuid.uuid4(),
        "starts_at": datetime(2030, 4, 1, start_hour, tzinfo=UTC),
        "ends_at": datetime(2030, 4, 1, start_hour + 1, tzinfo=UTC),
        "status": status,
        "reason_code": "SYNTHETIC",
        "cancellation_reason": "PATIENT_REQUEST" if status == "CANCELLED" else None,
        "version": 1,
        "created_by": uuid.uuid4(),
    }


def test_constraint_applies_only_to_active_statuses(app) -> None:
    provider = uuid.uuid4()
    with app.state.engine.begin() as connection:
        for status in ("CANCELLED", "NO_SHOW", "BOOKED"):
            connection.execute(insert(Appointment), [_row(provider, 9, status)])
    for status in ("BOOKED", "CHECKED_IN", "COMPLETED"):
        with pytest.raises(IntegrityError) as excinfo, app.state.engine.begin() as connection:
            connection.execute(insert(Appointment), [_row(provider, 9, status)])
        assert excinfo.value.orig.sqlstate == "23P01"
        assert PROVIDER_OVERLAP_CONSTRAINT in str(excinfo.value.orig)
