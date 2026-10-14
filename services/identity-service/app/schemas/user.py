import uuid
from datetime import datetime
from typing import Annotated

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    StringConstraints,
    model_validator,
)

from app.domain.roles import Permission, Role

PASSWORD_MIN_LENGTH = 12
PASSWORD_MAX_LENGTH = 128


def _validate_password(value: str) -> str:
    if not value.strip():
        raise ValueError("password must not be blank")
    return value


NormalizedEmail = Annotated[EmailStr, AfterValidator(str.lower)]
FullName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
NewPassword = Annotated[
    str,
    Field(min_length=PASSWORD_MIN_LENGTH, max_length=PASSWORD_MAX_LENGTH),
    AfterValidator(_validate_password),
]


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    full_name: str
    role: Role
    is_active: bool
    created_at: datetime
    updated_at: datetime
    last_login_at: datetime | None


class UserCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: NormalizedEmail
    full_name: FullName
    role: Role
    password: NewPassword
    is_active: bool = True


class UserUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    full_name: FullName | None = None
    role: Role | None = None
    is_active: bool | None = None

    @model_validator(mode="after")
    def _check_fields(self) -> "UserUpdate":
        if not self.model_fields_set:
            raise ValueError("at least one field must be provided")
        for name in self.model_fields_set:
            if getattr(self, name) is None:
                raise ValueError(f"{name} must not be null")
        return self


class PasswordReset(BaseModel):
    model_config = ConfigDict(extra="forbid")

    new_password: NewPassword


class RoleRead(BaseModel):
    name: Role
    description: str
    permissions: list[Permission]
