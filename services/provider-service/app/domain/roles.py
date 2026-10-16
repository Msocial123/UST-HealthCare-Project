"""Identity roles (from the token contract) and this service's server-side permission map."""

from enum import StrEnum


class Role(StrEnum):
    ADMIN = "ADMIN"
    RECEPTIONIST = "RECEPTIONIST"
    DOCTOR = "DOCTOR"
    READ_ONLY = "READ_ONLY"


class Permission(StrEnum):
    SPECIALTIES_READ = "specialties:read"
    SPECIALTIES_MANAGE = "specialties:manage"
    PROVIDERS_READ = "providers:read"
    PROVIDERS_MANAGE = "providers:manage"


ROLE_PERMISSIONS: dict[Role, frozenset[Permission]] = {
    Role.ADMIN: frozenset(Permission),
    Role.RECEPTIONIST: frozenset({Permission.SPECIALTIES_READ, Permission.PROVIDERS_READ}),
    Role.DOCTOR: frozenset({Permission.SPECIALTIES_READ, Permission.PROVIDERS_READ}),
    Role.READ_ONLY: frozenset({Permission.SPECIALTIES_READ}),
}


def has_permission(roles: frozenset[Role], permission: Permission) -> bool:
    return any(permission in ROLE_PERMISSIONS.get(role, frozenset()) for role in roles)
