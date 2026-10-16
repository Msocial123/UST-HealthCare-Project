"""Narrow HTTP contract with the Facility service: GET /api/v1/facilities/{id}.

Only `id`, `timezone` and `is_active` are used. The caller's access token is forwarded and never
logged. Scheduling never reads the Facility database.
"""

import logging
import uuid
from dataclasses import dataclass
from typing import Protocol
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import httpx
from pydantic import BaseModel, ConfigDict, ValidationError

from app.core.errors import NotFoundError, ServiceUnavailableError

logger = logging.getLogger(__name__)

FACILITY_UNAVAILABLE_MESSAGE = "Facility service is unavailable; try again later"


@dataclass(frozen=True)
class FacilityInfo:
    id: uuid.UUID
    timezone: str
    is_active: bool

    @property
    def zone(self) -> ZoneInfo:
        return ZoneInfo(self.timezone)


class FacilityClient(Protocol):
    def get_facility(self, facility_id: uuid.UUID, access_token: str) -> FacilityInfo:
        """Return facility metadata; raise NotFoundError (404) or ServiceUnavailableError (503)."""
        ...


class _FacilityPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: uuid.UUID
    timezone: str
    is_active: bool


def _unavailable(reason: str, **fields: object) -> ServiceUnavailableError:
    logger.warning(
        "facility_unavailable", extra={"event": "facility_unavailable", "reason": reason, **fields}
    )
    return ServiceUnavailableError(FACILITY_UNAVAILABLE_MESSAGE)


class HttpFacilityClient:
    def __init__(
        self, base_url: str, timeout_seconds: float, *, transport: httpx.BaseTransport | None = None
    ) -> None:
        self._client = httpx.Client(
            base_url=base_url.rstrip("/"),
            timeout=timeout_seconds,
            transport=transport,
            follow_redirects=False,
        )

    def get_facility(self, facility_id: uuid.UUID, access_token: str) -> FacilityInfo:
        try:
            response = self._client.get(
                f"/api/v1/facilities/{facility_id}",
                headers={"Authorization": f"Bearer {access_token}", "Accept": "application/json"},
            )
        except httpx.HTTPError as exc:
            raise _unavailable("transport_error", exc_type=type(exc).__name__) from None

        if response.status_code == 404:
            raise NotFoundError("Facility not found")
        if response.status_code != 200:
            raise _unavailable("unexpected_status", upstream_status=response.status_code)

        try:
            payload = _FacilityPayload.model_validate(response.json())
            ZoneInfo(payload.timezone)
        except (ValueError, ValidationError, ZoneInfoNotFoundError):
            raise _unavailable("invalid_response") from None
        if payload.id != facility_id:
            raise _unavailable("invalid_response")
        return FacilityInfo(id=payload.id, timezone=payload.timezone, is_active=payload.is_active)

    def close(self) -> None:
        self._client.close()
