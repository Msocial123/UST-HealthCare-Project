import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status

from app.api.deps import DbSession, require_permission
from app.domain.roles import Permission, Role
from app.models.user import User
from app.schemas.common import ErrorResponse, Page
from app.schemas.user import PasswordReset, UserCreate, UserRead, UserUpdate
from app.services.user_service import UserService

router = APIRouter(
    prefix="/users",
    tags=["users (admin)"],
    responses={401: {"model": ErrorResponse}, 403: {"model": ErrorResponse}},
)

UserReader = Annotated[User, Depends(require_permission(Permission.USERS_READ))]
UserManager = Annotated[User, Depends(require_permission(Permission.USERS_MANAGE))]


@router.get("", response_model=Page[UserRead], summary="List users (paginated, ordered by creation time)")
def list_users(
    db: DbSession,
    _: UserReader,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
    role: Annotated[Role | None, Query(description="Filter by role")] = None,
    is_active: Annotated[bool | None, Query(description="Filter by active status")] = None,
) -> Page[UserRead]:
    return UserService(db).list_users(limit=limit, offset=offset, role=role, is_active=is_active)


@router.post(
    "",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a user account",
    responses={409: {"model": ErrorResponse}},
)
def create_user(body: UserCreate, db: DbSession, actor: UserManager) -> UserRead:
    return UserRead.model_validate(UserService(db).create_user(body, actor=actor))


@router.get(
    "/{user_id}", response_model=UserRead, summary="Get a user", responses={404: {"model": ErrorResponse}}
)
def get_user(user_id: uuid.UUID, db: DbSession, _: UserReader) -> UserRead:
    return UserRead.model_validate(UserService(db).get_user(user_id))


@router.patch(
    "/{user_id}",
    response_model=UserRead,
    summary="Update name, role or active status",
    responses={404: {"model": ErrorResponse}, 409: {"model": ErrorResponse}},
)
def update_user(user_id: uuid.UUID, body: UserUpdate, db: DbSession, actor: UserManager) -> UserRead:
    return UserRead.model_validate(UserService(db).update_user(user_id, body, actor=actor))


@router.post(
    "/{user_id}/password",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Set a new password for a user",
    responses={404: {"model": ErrorResponse}},
)
def reset_password(user_id: uuid.UUID, body: PasswordReset, db: DbSession, actor: UserManager) -> Response:
    UserService(db).reset_password(user_id, body.new_password, actor=actor)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
