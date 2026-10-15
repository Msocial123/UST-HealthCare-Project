import uuid
from collections.abc import Sequence

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.domain.roles import Role
from app.models.user import User


class UserRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_id(self, user_id: uuid.UUID) -> User | None:
        return self._session.get(User, user_id)

    def get_by_email(self, email: str) -> User | None:
        return self._session.scalar(select(User).where(User.email == email.lower()))

    def list(
        self, *, limit: int, offset: int, role: Role | None = None, is_active: bool | None = None
    ) -> tuple[Sequence[User], int]:
        filters = []
        if role is not None:
            filters.append(User.role == role.value)
        if is_active is not None:
            filters.append(User.is_active.is_(is_active))
        total = self._session.scalar(select(func.count()).select_from(User).where(*filters)) or 0
        items = self._session.scalars(
            select(User).where(*filters).order_by(User.created_at, User.id).limit(limit).offset(offset)
        ).all()
        return items, total

    def lock_active_admins(self) -> Sequence[User]:
        """Lock every active ADMIN row (in id order) for the rest of the transaction.

        Concurrent transactions that change admin status serialize on these locks, so the
        "at least one active admin" invariant is checked against committed state.
        """
        statement = (
            select(User)
            .where(User.role == Role.ADMIN.value, User.is_active.is_(True))
            .order_by(User.id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        return self._session.scalars(statement).all()

    def add(self, user: User) -> User:
        self._session.add(user)
        self._session.flush()
        return user
