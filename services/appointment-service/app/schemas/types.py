"""Reusable constrained field types. Error messages never include the submitted value."""

from datetime import UTC, datetime
from typing import Annotated

from pydantic import AfterValidator, AwareDatetime, StringConstraints

from app.domain.appointments import REASON_CODE_PATTERN


def _to_utc(value: datetime) -> datetime:
    return value.astimezone(UTC)


UtcDatetime = Annotated[AwareDatetime, AfterValidator(_to_utc)]
ReasonCode = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=2, max_length=32, pattern=REASON_CODE_PATTERN),
    AfterValidator(str.upper),
]
