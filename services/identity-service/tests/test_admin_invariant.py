"""The system must always keep at least one active ADMIN, including under concurrent updates."""

import threading
import time

import pytest
from sqlalchemy import func, select

from app.core.errors import ConflictError
from app.domain.roles import Role
from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.schemas.user import UserUpdate
from app.services.user_service import UserService


def _active_admin_count(session) -> int:
    session.expire_all()
    return session.scalar(
        select(func.count()).select_from(User).where(User.role == Role.ADMIN.value, User.is_active.is_(True))
    )


@pytest.mark.parametrize("change", [{"is_active": False}, {"role": Role.READ_ONLY}])
def test_last_active_admin_cannot_be_removed_by_stale_admin(db_session, make_user, change: dict) -> None:
    alice = make_user(Role.ADMIN)
    bob = make_user(Role.ADMIN)
    service = UserService(db_session)

    service.update_user(bob.id, UserUpdate(role=Role.READ_ONLY), actor=alice)
    # Bob's request was authorized before his demotion committed; it must not remove Alice too.
    with pytest.raises(ConflictError, match="last active administrator"):
        service.update_user(alice.id, UserUpdate(**change), actor=bob)

    assert _active_admin_count(db_session) == 1


def test_admin_can_be_removed_while_another_remains(client, auth_headers, make_user) -> None:
    admin = make_user(Role.ADMIN)
    other = make_user(Role.ADMIN)
    response = client.patch(
        f"/api/v1/users/{other.id}", json={"is_active": False}, headers=auth_headers(user=admin)
    )
    assert response.status_code == 200


def test_disabled_admin_does_not_count_as_remaining_admin(db_session, make_user) -> None:
    alice = make_user(Role.ADMIN)
    bob = make_user(Role.ADMIN, is_active=False)
    with pytest.raises(ConflictError):
        UserService(db_session).update_user(alice.id, UserUpdate(role=Role.DOCTOR), actor=bob)


def test_concurrent_mutual_demotion_keeps_one_admin(app, make_user) -> None:
    if app.state.engine.dialect.name != "postgresql":
        pytest.skip("row locking needs PostgreSQL (set TEST_DATABASE_URL)")
    alice = make_user(Role.ADMIN)
    bob = make_user(Role.ADMIN)
    first = app.state.session_factory()
    second = app.state.session_factory()
    outcome: dict[str, object] = {}

    def bob_disables_alice() -> None:
        try:
            UserService(second).update_user(alice.id, UserUpdate(is_active=False), actor=bob)
            outcome["result"] = "updated"
        except ConflictError:
            outcome["result"] = "conflict"

    try:
        UserRepository(first).lock_active_admins()  # hold the admin locks so the race is deterministic
        worker = threading.Thread(target=bob_disables_alice)
        worker.start()
        time.sleep(0.5)
        assert worker.is_alive(), "second transaction should wait on the admin row locks"
        UserService(first).update_user(bob.id, UserUpdate(role=Role.READ_ONLY), actor=alice)
        worker.join(timeout=10)
        assert outcome["result"] == "conflict"
        assert _active_admin_count(first) == 1
    finally:
        first.close()
        second.close()
