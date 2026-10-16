"""Identity roles (from the token contract) and this service's server-side permission map."""

from enum import StrEnum


class Role(StrEnum):
    ADMIN = "ADMIN"
    RECEPTIONIST = "RECEPTIONIST"
    DOCTOR = "DOCTOR"
    READ_ONLY = "READ_ONLY"


class Permission(StrEnum):
    FACILITIES_READ = "facilities:read"
    FACILITIES_MANAGE = "facilities:manage"


_READ = frozenset({Permission.FACILITIES_READ})

ROLE_PERMISSIONS: dict[Role, frozenset[Permission]] = {
    Role.ADMIN: frozenset(Permission),
    Role.RECEPTIONIST: _READ,
    Role.DOCTOR: _READ,
    Role.READ_ONLY: _READ,
}


def has_permission(roles: frozenset[Role], permission: Permission) -> bool:
    return any(permission in ROLE_PERMISSIONS.get(role, frozenset()) for role in roles)
