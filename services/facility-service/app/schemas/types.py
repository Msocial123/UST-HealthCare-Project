"""Reusable constrained field types. Error messages never include the submitted value."""

from typing import Annotated

from pydantic import AfterValidator, StringConstraints
from pydantic_core import PydanticCustomError

from app.domain.facilities import is_valid_timezone


def _validate_timezone(value: str) -> str:
    if not is_valid_timezone(value):
        raise PydanticCustomError("invalid_timezone", "Must be a valid IANA timezone name, e.g. Asia/Kolkata")
    return value


Code = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=2, max_length=32, pattern=r"^[A-Za-z0-9_-]+$"),
    AfterValidator(str.upper),
]
Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=200)]
AddressLine = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
Locality = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
PostalCode = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=2, max_length=16, pattern=r"^[A-Za-z0-9 -]+$")
]
CountryCode = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=2, max_length=2, pattern=r"^[A-Za-z]{2}$"),
    AfterValidator(str.upper),
]
Phone = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True, min_length=7, max_length=32, pattern=r"^\+?[0-9][0-9 ()-]{5,30}$"
    ),
]
Timezone = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=64),
    AfterValidator(_validate_timezone),
]
Floor = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=16, pattern=r"^[A-Za-z0-9 -]+$")
]
PhoneExtension = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=10, pattern=r"^[0-9]+$")
]
RoomNumber = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=16, pattern=r"^[A-Za-z0-9-]+$"),
    AfterValidator(str.upper),
]
