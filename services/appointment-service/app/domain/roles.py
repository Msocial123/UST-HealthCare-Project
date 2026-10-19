"""Identity roles (from the token contract) and this service's server-side permission map."""

from enum import StrEnum


class Role(StrEnum):
    ADMIN = "ADMIN"
    RECEPTIONIST = "RECEPTIONIST"
    DOCTOR = "DOCTOR"
    READ_ONLY = "READ_ONLY"


class Permission(StrEnum):
    APPOINTMENTS_READ = "appointments:read"
    APPOINTMENTS_BOOK = "appointments:book"  # book, reschedule, cancel
    APPOINTMENTS_TRANSITION = "appointments:transition"  # check-in, complete, no-show


ROLE_PERMISSIONS: dict[Role, frozenset[Permission]] = {
    Role.ADMIN: frozenset(Permission),
    Role.RECEPTIONIST: frozenset(Permission),
    Role.DOCTOR: frozenset({Permission.APPOINTMENTS_READ, Permission.APPOINTMENTS_TRANSITION}),
    Role.READ_ONLY: frozenset(),
}


def has_permission(roles: frozenset[Role], permission: Permission) -> bool:
    return any(permission in ROLE_PERMISSIONS.get(role, frozenset()) for role in roles)
