"""Narrow, optional HTTP contract with the Scheduling service: GET /api/v1/providers/{id}/slots.

Scheduling availability is advisory. This service still enforces booking integrity with its own
database exclusion constraint. The caller's access token is forwarded and never logged.
"""

import logging
import uuid
from datetime import datetime, timedelta
from typing import Protocol

import httpx
from pydantic import AwareDatetime, BaseModel, ConfigDict, ValidationError

from app.core.errors import ConflictError, NotFoundError, ServiceUnavailableError
from app.domain.appointments import interval_covered

logger = logging.getLogger(__name__)

SCHEDULING_UNAVAILABLE_MESSAGE = "Scheduling service is unavailable; try again later"


class SchedulingClient(Protocol):
    def is_available(
        self,
        provider_id: uuid.UUID,
        facility_id: uuid.UUID,
        starts_at: datetime,
        ends_at: datetime,
        access_token: str,
    ) -> bool:
        """True when advisory slots cover [starts_at, ends_at). Raises 404/409/503 errors."""
        ...


class _Slot(BaseModel):
    model_config = ConfigDict(extra="ignore")

    start_utc: AwareDatetime
    end_utc: AwareDatetime


class _SlotsPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")

    slots: list[_Slot]


def _unavailable(reason: str, **fields: object) -> ServiceUnavailableError:
    logger.warning(
        "scheduling_unavailable", extra={"event": "scheduling_unavailable", "reason": reason, **fields}
    )
    return ServiceUnavailableError(SCHEDULING_UNAVAILABLE_MESSAGE)


class HttpSchedulingClient:
    def __init__(
        self, base_url: str, timeout_seconds: float, *, transport: httpx.BaseTransport | None = None
    ) -> None:
        self._client = httpx.Client(
            base_url=base_url.rstrip("/"),
            timeout=timeout_seconds,
            transport=transport,
            follow_redirects=False,
        )

    def is_available(
        self,
        provider_id: uuid.UUID,
        facility_id: uuid.UUID,
        starts_at: datetime,
        ends_at: datetime,
        access_token: str,
    ) -> bool:
        # Slot queries take facility-local dates; one day either side of the UTC dates covers any offset.
        params = {
            "facility_id": str(facility_id),
            "date_from": (starts_at - timedelta(days=1)).date().isoformat(),
            "date_to": (ends_at + timedelta(days=1)).date().isoformat(),
        }
        try:
            response = self._client.get(
                f"/api/v1/providers/{provider_id}/slots",
                params=params,
                headers={"Authorization": f"Bearer {access_token}", "Accept": "application/json"},
            )
        except httpx.HTTPError as exc:
            raise _unavailable("transport_error", exc_type=type(exc).__name__) from None

        if response.status_code == 404:
            raise NotFoundError("Facility not found")
        if response.status_code == 409:
            raise ConflictError("Facility is inactive")
        if response.status_code != 200:
            raise _unavailable("unexpected_status", upstream_status=response.status_code)
        try:
            payload = _SlotsPayload.model_validate(response.json())
        except (ValueError, ValidationError):
            raise _unavailable("invalid_response") from None
        windows = [(slot.start_utc, slot.end_utc) for slot in payload.slots]
        return interval_covered(windows, starts_at, ends_at)

    def close(self) -> None:
        self._client.close()
