"""Schemas for authentication endpoints.

RegisterRequest / LoginRequest
    Inbound payloads for /auth/register and /auth/login.

TokenResponse
    Returned on successful register or login.  ``access_token`` is a signed
    HS256 JWT; ``token_type`` is always ``"bearer"``.  The client should store
    the token in ``sessionStorage`` and send it as
    ``Authorization: Bearer <token>`` on subsequent requests.
"""
from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    email: EmailStr = Field(description="Account email address — used as login identifier.")
    password: str = Field(min_length=8, description="Password, minimum 8 characters.")


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str = Field(description="Signed JWT access token.")
    token_type: str = Field(default="bearer")
    user_id: str = Field(description="UUID of the authenticated user.")
