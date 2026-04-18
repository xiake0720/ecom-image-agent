"""FastAPI 依赖注入集合。"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.exceptions import AppException
from backend.core.request_context import RequestContext
from backend.db.models.user import User
from backend.db.session import get_db_session
from backend.services.auth_service import AuthService


bearer_scheme = HTTPBearer(auto_error=False)


async def get_auth_service(session: Annotated[AsyncSession, Depends(get_db_session)]) -> AuthService:
    """按请求构造认证服务。"""

    return AuthService(session)


def get_request_context(request: Request) -> RequestContext:
    """提取审计和认证所需的请求上下文。"""

    client_host = request.client.host if request.client is not None else None
    return RequestContext(
        request_id=getattr(request.state, "request_id", ""),
        ip_address=client_host,
        user_agent=request.headers.get("user-agent"),
        device_id=request.headers.get("x-device-id"),
    )


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> User:
    """Bearer access token 依赖。"""

    if credentials is None or credentials.scheme.lower() != "bearer":
        raise AppException("缺少 access token", code=4014, status_code=401)
    return await auth_service.get_current_user(credentials.credentials)


async def get_current_user_optional(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> User | None:
    """兼容旧生成接口：有 token 时解析用户，无 token 时回退匿名兼容模式。"""

    if credentials is None:
        return None
    if credentials.scheme.lower() != "bearer":
        raise AppException("access token 类型无效", code=4015, status_code=401)
    return await auth_service.get_current_user(credentials.credentials)
