import logging
import uuid

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import ConflictError, NotFoundError
from app.core.passwords import hash_password
from app.domain.roles import Role
from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.schemas.common import Page
from app.schemas.user import UserCreate, UserRead, UserUpdate

logger = logging.getLogger(__name__)


class UserService:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._users = UserRepository(session)

    def list_users(
        self, *, limit: int, offset: int, role: Role | None = None, is_active: bool | None = None
    ) -> Page[UserRead]:
        items, total = self._users.list(limit=limit, offset=offset, role=role, is_active=is_active)
        return Page[UserRead](
            items=[UserRead.model_validate(user) for user in items], total=total, limit=limit, offset=offset
        )

    def get_user(self, user_id: uuid.UUID) -> User:
        user = self._users.get_by_id(user_id)
        if user is None:
            raise NotFoundError("User not found")
        return user

    def create_user(self, data: UserCreate, *, actor: User) -> User:
        if self._users.get_by_email(data.email) is not None:
            raise ConflictError("A user with this email already exists")
        user = User(
            email=data.email,
            full_name=data.full_name,
            role=data.role.value,
            is_active=data.is_active,
            password_hash=hash_password(data.password),
        )
        try:
            self._users.add(user)
            self._session.commit()
        except IntegrityError:
            self._session.rollback()
            raise ConflictError("A user with this email already exists") from None
        logger.info(
            "user_created",
            extra={
                "event": "user_created",
                "user_id": str(user.id),
                "role": user.role,
                "actor_id": str(actor.id),
            },
        )
        return user

    def update_user(self, user_id: uuid.UUID, data: UserUpdate, *, actor: User) -> User:
        user = self.get_user(user_id)
        changes = data.model_dump(exclude_unset=True)
        if user.id == actor.id:
            if changes.get("is_active") is False:
                raise ConflictError("Administrators cannot disable their own account")
            if "role" in changes and changes["role"] != Role.ADMIN:
                raise ConflictError("Administrators cannot remove their own ADMIN role")
        if "full_name" in changes:
            user.full_name = changes["full_name"]
        if "role" in changes:
            user.role = Role(changes["role"]).value
        if "is_active" in changes:
            user.is_active = changes["is_active"]
        self._session.commit()
        logger.info(
            "user_updated",
            extra={
                "event": "user_updated",
                "user_id": str(user.id),
                "fields": sorted(changes),
                "actor_id": str(actor.id),
            },
        )
        return user

    def reset_password(self, user_id: uuid.UUID, new_password: str, *, actor: User) -> None:
        user = self.get_user(user_id)
        user.password_hash = hash_password(new_password)
        self._session.commit()
        logger.info(
            "user_password_reset",
            extra={"event": "user_password_reset", "user_id": str(user.id), "actor_id": str(actor.id)},
        )
