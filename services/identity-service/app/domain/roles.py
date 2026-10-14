"""Demo roles and identity-service permissions.

Roles are emitted in access tokens. Each downstream service maps roles to its own permissions;
the permissions below govern only the identity service's own endpoints.
"""

from enum import StrEnum


class Role(StrEnum):
    ADMIN = "ADMIN"
    RECEPTIONIST = "RECEPTIONIST"
    DOCTOR = "DOCTOR"
    READ_ONLY = "READ_ONLY"


class Permission(StrEnum):
    ROLES_READ = "roles:read"
    USERS_READ = "users:read"
    USERS_MANAGE = "users:manage"


ROLE_DESCRIPTIONS: dict[Role, str] = {
    Role.ADMIN: "System administrator: manages user accounts and role assignments.",
    Role.RECEPTIONIST: (
        "Front-desk staff: patient registration and appointment administration (future services)."
    ),
    Role.DOCTOR: "Clinician: views schedules and records administrative visit information (future services).",
    Role.READ_ONLY: "Read-only access to non-sensitive administrative data (future services).",
}

ROLE_PERMISSIONS: dict[Role, frozenset[Permission]] = {
    Role.ADMIN: frozenset(Permission),
    Role.RECEPTIONIST: frozenset({Permission.ROLES_READ}),
    Role.DOCTOR: frozenset({Permission.ROLES_READ}),
    Role.READ_ONLY: frozenset({Permission.ROLES_READ}),
}


def has_permission(role: Role, permission: Permission) -> bool:
    return permission in ROLE_PERMISSIONS.get(role, frozenset())
