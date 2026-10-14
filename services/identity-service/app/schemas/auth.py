from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.user import NormalizedEmail


class LoginRequest(BaseModel):
    email: NormalizedEmail
    password: str = Field(min_length=1, max_length=128)


class TokenResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"  # noqa: S105
    expires_in: int = Field(description="Token lifetime in seconds")
