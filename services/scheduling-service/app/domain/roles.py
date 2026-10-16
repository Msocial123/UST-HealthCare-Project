"""Identity roles (from the token contract) and this service's server-side permission map."""

from enum import StrEnum


class Role(StrEnum):
    ADMIN = "ADMIN"
    RECEPTIONIST = "RECEPTIONIST"
    DOCTOR = "DOCTOR"
    READ_ONLY = "READ_ONLY"


class Permission(StrEnum):
    SCHEDULE_READ = "schedule:read"
    WORKING_HOURS_MANAGE = "working_hours:manage"
    EXCEPTIONS_MANAGE = "exceptions:manage"
    SLOTS_READ = "slots:read"


ROLE_PERMISSIONS: dict[Role, frozenset[Permission]] = {
    Role.ADMIN: frozenset(Permission),
    Role.RECEPTIONIST: frozenset(
        {Permission.SCHEDULE_READ, Permission.EXCEPTIONS_MANAGE, Permission.SLOTS_READ}
    ),
    Role.DOCTOR: frozenset({Permission.SCHEDULE_READ, Permission.SLOTS_READ}),
    Role.READ_ONLY: frozenset({Permission.SCHEDULE_READ}),
}


def has_permission(roles: frozenset[Role], permission: Permission) -> bool:
    return any(permission in ROLE_PERMISSIONS.get(role, frozenset()) for role in roles)
