"""Authentication request/response models."""

from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    """New account credentials."""

    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class LoginRequest(BaseModel):
    """Login credentials."""

    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class TokenResponse(BaseModel):
    """OAuth2-style bearer token payload."""

    access_token: str
    token_type: str = "bearer"


class UserPublic(BaseModel):
    """Public user fields."""

    id: int
    email: str

    model_config = {"from_attributes": True}
