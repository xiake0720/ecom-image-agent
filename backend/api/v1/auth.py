"""API v1 认证路由。"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response

from backend.api.dependencies import get_auth_service, get_current_user, get_request_context
from backend.core.config import get_settings
from backend.core.request_context import RequestContext
from backend.core.response import success_response
from backend.core.security import clear_refresh_cookie, set_refresh_cookie
from backend.db.models.user import User
from backend.schemas.auth import AuthTokenResponse, LoginRequest, LogoutResponse, RegisterRequest, UserProfileResponse
from backend.services.auth_service import AuthService


router = APIRouter(prefix="/auth", tags=["auth-v1"])


@router.post("/register")
async def register(
    payload: RegisterRequest,
    request: Request,
    response: Response,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
    context: Annotated[RequestContext, Depends(get_request_context)],
) -> dict[str, object]:
    """注册新用户，并立即签发登录态。"""

    settings = get_settings()
    result = await auth_service.register(payload, context=context)
    set_refresh_cookie(response, result.refresh_token, settings=settings)
    data = AuthTokenResponse(
        access_token=result.access_token,
        expires_in=result.expires_in,
        user=UserProfileResponse.model_validate(result.user),
    )
    return success_response(data.model_dump(mode="json"), request.state.request_id, message="注册成功")


@router.post("/login")
async def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
    context: Annotated[RequestContext, Depends(get_request_context)],
) -> dict[str, object]:
    """账号密码登录。"""

    settings = get_settings()
    result = await auth_service.login(payload, context=context)
    set_refresh_cookie(response, result.refresh_token, settings=settings)
    data = AuthTokenResponse(
        access_token=result.access_token,
        expires_in=result.expires_in,
        user=UserProfileResponse.model_validate(result.user),
    )
    return success_response(data.model_dump(mode="json"), request.state.request_id, message="登录成功")


@router.post("/refresh")
async def refresh(
    request: Request,
    response: Response,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
    context: Annotated[RequestContext, Depends(get_request_context)],
) -> dict[str, object]:
    """用 HttpOnly refresh cookie 轮换 access token。"""

    settings = get_settings()
    refresh_token = request.cookies.get(settings.auth_refresh_cookie_name)
    result = await auth_service.refresh(refresh_token, context=context)
    set_refresh_cookie(response, result.refresh_token, settings=settings)
    data = AuthTokenResponse(
        access_token=result.access_token,
        expires_in=result.expires_in,
        user=UserProfileResponse.model_validate(result.user),
    )
    return success_response(data.model_dump(mode="json"), request.state.request_id, message="刷新成功")


@router.post("/logout")
async def logout(
    request: Request,
    response: Response,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
    context: Annotated[RequestContext, Depends(get_request_context)],
) -> dict[str, object]:
    """撤销当前 refresh token，并清理 cookie。"""

    settings = get_settings()
    refresh_token = request.cookies.get(settings.auth_refresh_cookie_name)
    logged_out = await auth_service.logout(refresh_token, context=context)
    clear_refresh_cookie(response, settings=settings)
    data = LogoutResponse(logged_out=logged_out)
    return success_response(data.model_dump(mode="json"), request.state.request_id, message="已登出")


@router.get("/me")
async def me(request: Request, current_user: Annotated[User, Depends(get_current_user)]) -> dict[str, object]:
    """返回当前 access token 对应的用户信息。"""

    data = UserProfileResponse.model_validate(current_user)
    return success_response(data.model_dump(mode="json"), request.state.request_id)
