"""认证模块 Pydantic Schema。"""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class RegisterRequest(BaseModel):
    """用户注册请求。"""

    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    nickname: str | None = Field(default=None, max_length=100)

    @field_validator("email")
    @classmethod
    def _normalize_email(cls, value: EmailStr) -> str:
        return str(value).strip().lower()


class LoginRequest(BaseModel):
    """用户登录请求。"""

    email: EmailStr
    password: str = Field(min_length=8, max_length=128)

    @field_validator("email")
    @classmethod
    def _normalize_email(cls, value: EmailStr) -> str:
        return str(value).strip().lower()


class UserProfileResponse(BaseModel):
    """对前端暴露的最小用户信息。"""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: EmailStr
    nickname: str | None = None
    avatar_url: str | None = None
    status: str
    email_verified: bool
    last_login_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class AuthTokenResponse(BaseModel):
    """登录态返回体。"""

    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int
    user: UserProfileResponse


class LogoutResponse(BaseModel):
    """登出返回体。"""

    logged_out: bool = True
