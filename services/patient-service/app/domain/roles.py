"""Identity-service roles and the patient service's own role -> permission map.

Roles come from verified access tokens; permissions are decided here, server-side. Unknown or
unmapped roles get no permissions (default deny).
"""

from collections.abc import Iterable
from enum import StrEnum


class Role(StrEnum):
    ADMIN = "ADMIN"
    RECEPTIONIST = "RECEPTIONIST"
    DOCTOR = "DOCTOR"
    READ_ONLY = "READ_ONLY"


class Permission(StrEnum):
    PATIENTS_READ = "patients:read"
    PATIENTS_WRITE = "patients:write"
    PATIENTS_DEACTIVATE = "patients:deactivate"


ROLE_PERMISSIONS: dict[Role, frozenset[Permission]] = {
    Role.ADMIN: frozenset(Permission),
    Role.RECEPTIONIST: frozenset({Permission.PATIENTS_READ, Permission.PATIENTS_WRITE}),
    Role.DOCTOR: frozenset({Permission.PATIENTS_READ}),
    Role.READ_ONLY: frozenset(),
}


def permissions_for(roles: Iterable[Role]) -> frozenset[Permission]:
    granted: set[Permission] = set()
    for role in roles:
        granted |= ROLE_PERMISSIONS.get(role, frozenset())
    return frozenset(granted)
