from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.deps import require_permission
from app.domain.roles import ROLE_DESCRIPTIONS, ROLE_PERMISSIONS, Permission, Role
from app.models.user import User
from app.schemas.common import ErrorResponse
from app.schemas.user import RoleRead

router = APIRouter(prefix="/roles", tags=["roles"])


@router.get(
    "",
    response_model=list[RoleRead],
    summary="List demo roles and the identity-service permissions they grant",
    responses={401: {"model": ErrorResponse}, 403: {"model": ErrorResponse}},
)
def list_roles(_: Annotated[User, Depends(require_permission(Permission.ROLES_READ))]) -> list[RoleRead]:
    return [
        RoleRead(name=role, description=ROLE_DESCRIPTIONS[role], permissions=sorted(ROLE_PERMISSIONS[role]))
        for role in Role
    ]
