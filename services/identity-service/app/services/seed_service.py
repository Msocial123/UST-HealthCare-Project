"""Development-only seeding of fictional demo accounts."""

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.core.passwords import hash_password
from app.domain.roles import Role
from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.schemas.user import PASSWORD_MIN_LENGTH


@dataclass(frozen=True)
class DemoAccount:
    email: str
    full_name: str
    role: Role


DEMO_ACCOUNTS: tuple[DemoAccount, ...] = (
    DemoAccount("admin@demo.smarthospital.example", "Demo Admin (Fictional)", Role.ADMIN),
    DemoAccount("reception@demo.smarthospital.example", "Demo Receptionist (Fictional)", Role.RECEPTIONIST),
    DemoAccount("doctor@demo.smarthospital.example", "Dr. Demo Doctor (Fictional)", Role.DOCTOR),
    DemoAccount("readonly@demo.smarthospital.example", "Demo Read-Only User (Fictional)", Role.READ_ONLY),
)


@dataclass(frozen=True)
class SeedResult:
    email: str
    role: Role
    created: bool


def seed_demo_users(session: Session, password: str) -> list[SeedResult]:
    """Create missing demo accounts. Existing accounts are left untouched (idempotent)."""
    if len(password) < PASSWORD_MIN_LENGTH:
        raise ValueError(f"demo password must be at least {PASSWORD_MIN_LENGTH} characters")
    users = UserRepository(session)
    results: list[SeedResult] = []
    for account in DEMO_ACCOUNTS:
        if users.get_by_email(account.email) is not None:
            results.append(SeedResult(account.email, account.role, created=False))
            continue
        users.add(
            User(
                email=account.email,
                full_name=account.full_name,
                role=account.role.value,
                password_hash=hash_password(password),
                is_active=True,
            )
        )
        results.append(SeedResult(account.email, account.role, created=True))
    session.commit()
    return results
