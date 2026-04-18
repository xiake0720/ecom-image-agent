"""认证安全工具。"""

from __future__ import annotations

import base64
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import secrets
import uuid

import jwt
from fastapi import Response
from jwt import InvalidTokenError

from backend.core.config import Settings, get_settings


SCRYPT_N = 2**14
SCRYPT_R = 8
SCRYPT_P = 1
SCRYPT_KEY_LENGTH = 64


@dataclass(frozen=True, slots=True)
class AccessTokenPayload:
    """解码后的 access token 载荷。"""

    user_id: uuid.UUID
    token_id: str
    expires_at: datetime


def hash_password(password: str) -> str:
    """使用 scrypt 生成密码哈希，避免明文持久化。"""

    salt = secrets.token_bytes(16)
    derived_key = hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=SCRYPT_N,
        r=SCRYPT_R,
        p=SCRYPT_P,
        dklen=SCRYPT_KEY_LENGTH,
    )
    salt_b64 = base64.urlsafe_b64encode(salt).decode("ascii")
    hash_b64 = base64.urlsafe_b64encode(derived_key).decode("ascii")
    return f"scrypt${SCRYPT_N}${SCRYPT_R}${SCRYPT_P}${salt_b64}${hash_b64}"


def verify_password(password: str, password_hash: str) -> bool:
    """校验密码与持久化哈希是否匹配。"""

    try:
        algorithm, n_value, r_value, p_value, salt_b64, hash_b64 = password_hash.split("$", maxsplit=5)
    except ValueError:
        return False
    if algorithm != "scrypt":
        return False

    salt = base64.urlsafe_b64decode(salt_b64.encode("ascii"))
    expected = base64.urlsafe_b64decode(hash_b64.encode("ascii"))
    actual = hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=int(n_value),
        r=int(r_value),
        p=int(p_value),
        dklen=len(expected),
    )
    return hmac.compare_digest(actual, expected)


def create_access_token(*, user_id: uuid.UUID, settings: Settings | None = None) -> tuple[str, int]:
    """生成 access token。"""

    effective_settings = settings or get_settings()
    issued_at = datetime.now(timezone.utc)
    expires_in = effective_settings.auth_access_token_expire_minutes * 60
    expires_at = issued_at + timedelta(seconds=expires_in)
    payload = {
        "sub": str(user_id),
        "jti": uuid.uuid4().hex,
        "typ": "access",
        "iat": int(issued_at.timestamp()),
        "exp": int(expires_at.timestamp()),
    }
    token = jwt.encode(payload, effective_settings.auth_jwt_secret_key, algorithm=effective_settings.auth_jwt_algorithm)
    return token, expires_in


def decode_access_token(token: str, *, settings: Settings | None = None) -> AccessTokenPayload:
    """校验并解码 access token。"""

    effective_settings = settings or get_settings()
    try:
        payload = jwt.decode(token, effective_settings.auth_jwt_secret_key, algorithms=[effective_settings.auth_jwt_algorithm])
    except InvalidTokenError as exc:
        raise ValueError("invalid access token") from exc

    if payload.get("typ") != "access":
        raise ValueError("invalid token type")

    exp = payload.get("exp")
    sub = payload.get("sub")
    jti = payload.get("jti")
    if not isinstance(exp, int) or not isinstance(sub, str) or not isinstance(jti, str):
        raise ValueError("invalid token payload")

    return AccessTokenPayload(
        user_id=uuid.UUID(sub),
        token_id=jti,
        expires_at=datetime.fromtimestamp(exp, tz=timezone.utc),
    )


def generate_refresh_token() -> str:
    """生成发送到 HttpOnly cookie 的 refresh token 原文。"""

    return secrets.token_urlsafe(48)


def hash_refresh_token(token: str, *, settings: Settings | None = None) -> str:
    """对 refresh token 原文做带密钥的哈希。"""

    effective_settings = settings or get_settings()
    return hashlib.sha256(f"{effective_settings.auth_token_hash_secret}:{token}".encode("utf-8")).hexdigest()


def set_refresh_cookie(response: Response, refresh_token: str, *, settings: Settings | None = None) -> None:
    """写入 HttpOnly refresh cookie。"""

    effective_settings = settings or get_settings()
    response.set_cookie(
        key=effective_settings.auth_refresh_cookie_name,
        value=refresh_token,
        max_age=effective_settings.auth_refresh_token_expire_days * 24 * 60 * 60,
        httponly=True,
        secure=effective_settings.auth_refresh_cookie_secure,
        samesite=effective_settings.auth_refresh_cookie_samesite,
        domain=effective_settings.auth_refresh_cookie_domain,
        path=effective_settings.auth_refresh_cookie_path,
    )


def clear_refresh_cookie(response: Response, *, settings: Settings | None = None) -> None:
    """清理 refresh cookie。"""

    effective_settings = settings or get_settings()
    response.delete_cookie(
        key=effective_settings.auth_refresh_cookie_name,
        domain=effective_settings.auth_refresh_cookie_domain,
        path=effective_settings.auth_refresh_cookie_path,
        httponly=True,
        secure=effective_settings.auth_refresh_cookie_secure,
        samesite=effective_settings.auth_refresh_cookie_samesite,
    )
