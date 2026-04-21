"""认证业务服务。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import logging
from time import perf_counter
import uuid

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.config import get_settings
from backend.core.exceptions import AppException
from backend.core.logging import format_log_event
from backend.core.request_context import RequestContext
from backend.core.security import create_access_token, decode_access_token, generate_refresh_token, hash_password, hash_refresh_token, verify_password
from backend.db.enums import AuditAction, UserStatus
from backend.db.models.audit import AuditLog
from backend.db.models.auth import RefreshToken
from backend.db.models.user import User
from backend.repositories.db.audit_log_repository import AuditLogRepository
from backend.repositories.db.refresh_token_repository import RefreshTokenRepository
from backend.repositories.db.user_repository import UserRepository
from backend.schemas.auth import LoginRequest, RegisterRequest


logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class AuthSessionBundle:
    """认证接口统一返回的数据载体。"""

    access_token: str
    expires_in: int
    refresh_token: str
    user: User


class AuthService:
    """处理注册、登录、刷新和当前用户查询。"""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.settings = get_settings()
        self.user_repo = UserRepository(session)
        self.refresh_token_repo = RefreshTokenRepository(session)
        self.audit_log_repo = AuditLogRepository(session)

    async def register(self, payload: RegisterRequest, *, context: RequestContext) -> AuthSessionBundle:
        """注册用户并签发首个登录态。"""

        started_at = perf_counter()
        logger.info(format_log_event("auth_register_started", request_id=context.request_id))
        phase = "query"
        try:
            existing = await self.user_repo.get_by_email(payload.email)
            if existing is not None:
                logger.warning(
                    format_log_event(
                        "auth_register_failed",
                        request_id=context.request_id,
                        phase=phase,
                        reason="email_already_registered",
                        elapsed_ms=_elapsed_ms(started_at),
                    )
                )
                raise AppException("邮箱已注册", code=4091, status_code=409)

            phase = "user_create"
            now = datetime.now(timezone.utc)
            user = User(
                id=uuid.uuid4(),
                email=payload.email,
                password_hash=hash_password(payload.password),
                nickname=payload.nickname,
                status=UserStatus.ACTIVE.value,
                last_login_at=now,
                last_login_ip=context.ip_address,
            )
            logger.info(
                format_log_event(
                    "auth_register_user_created",
                    request_id=context.request_id,
                    user_id=user.id.hex,
                    elapsed_ms=_elapsed_ms(started_at),
                )
            )

            access_token, expires_in = create_access_token(user_id=user.id, settings=self.settings)
            raw_refresh_token = generate_refresh_token()
            phase = "refresh_token_create"
            refresh_record = self._build_refresh_token_record(user=user, raw_token=raw_refresh_token, context=context, issued_at=now)
            logger.info(
                format_log_event(
                    "auth_register_refresh_token_created",
                    request_id=context.request_id,
                    user_id=user.id.hex,
                    refresh_token_id=refresh_record.id.hex,
                    elapsed_ms=_elapsed_ms(started_at),
                )
            )

            self.user_repo.add(user)
            await self.session.flush()
            self.refresh_token_repo.add(refresh_record)
            self.audit_log_repo.add(
                self._build_audit_log(
                    action=AuditAction.AUTH_REGISTER.value,
                    user_id=user.id,
                    object_type="user",
                    object_id=user.id,
                    context=context,
                    payload={"email": user.email},
                )
            )
            phase = "commit"
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            logger.exception(
                format_log_event(
                    "auth_register_failed",
                    request_id=context.request_id,
                    phase=phase,
                    elapsed_ms=_elapsed_ms(started_at),
                )
            )
            raise AppException("用户注册失败，请稍后重试", code=5001, status_code=500) from exc
        except AppException:
            raise
        except Exception:
            await self.session.rollback()
            logger.exception(
                format_log_event(
                    "auth_register_failed",
                    request_id=context.request_id,
                    phase=phase,
                    elapsed_ms=_elapsed_ms(started_at),
                )
            )
            raise
        await self.session.refresh(user)
        logger.info(
            format_log_event(
                "auth_register_committed",
                request_id=context.request_id,
                user_id=user.id.hex,
                elapsed_ms=_elapsed_ms(started_at),
            )
        )
        return AuthSessionBundle(access_token=access_token, expires_in=expires_in, refresh_token=raw_refresh_token, user=user)

    async def login(self, payload: LoginRequest, *, context: RequestContext) -> AuthSessionBundle:
        """校验邮箱密码并签发登录态。"""

        started_at = perf_counter()
        logger.info(format_log_event("auth_login_started", request_id=context.request_id))
        phase = "query"
        try:
            user = await self.user_repo.get_by_email(payload.email)
            if user is None or not verify_password(payload.password, user.password_hash):
                logger.warning(
                    format_log_event(
                        "auth_login_failed",
                        request_id=context.request_id,
                        phase=phase,
                        reason="invalid_credentials",
                        elapsed_ms=_elapsed_ms(started_at),
                    )
                )
                raise AppException("邮箱或密码错误", code=4011, status_code=401)
            self._ensure_user_is_active(user)

            now = datetime.now(timezone.utc)
            access_token, expires_in = create_access_token(user_id=user.id, settings=self.settings)
            raw_refresh_token = generate_refresh_token()
            phase = "refresh_token_create"
            refresh_record = self._build_refresh_token_record(user=user, raw_token=raw_refresh_token, context=context, issued_at=now)

            user.last_login_at = now
            user.last_login_ip = context.ip_address
            self.refresh_token_repo.add(refresh_record)
            self.audit_log_repo.add(
                self._build_audit_log(
                    action=AuditAction.AUTH_LOGIN.value,
                    user_id=user.id,
                    object_type="user",
                    object_id=user.id,
                    context=context,
                    payload={"email": user.email},
                )
            )
            phase = "commit"
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            logger.exception(
                format_log_event(
                    "auth_login_failed",
                    request_id=context.request_id,
                    phase=phase,
                    elapsed_ms=_elapsed_ms(started_at),
                )
            )
            raise AppException("登录失败，请稍后重试", code=5002, status_code=500) from exc
        except AppException:
            raise
        except Exception:
            await self.session.rollback()
            logger.exception(
                format_log_event(
                    "auth_login_failed",
                    request_id=context.request_id,
                    phase=phase,
                    elapsed_ms=_elapsed_ms(started_at),
                )
            )
            raise
        await self.session.refresh(user)
        logger.info(
            format_log_event(
                "auth_login_succeeded",
                request_id=context.request_id,
                user_id=user.id.hex,
                elapsed_ms=_elapsed_ms(started_at),
            )
        )

        return AuthSessionBundle(access_token=access_token, expires_in=expires_in, refresh_token=raw_refresh_token, user=user)

    async def refresh(self, raw_refresh_token: str | None, *, context: RequestContext) -> AuthSessionBundle:
        """校验 refresh token，并执行轮换。"""

        started_at = perf_counter()
        logger.info(format_log_event("auth_refresh_started", request_id=context.request_id))
        phase = "validate_token"
        try:
            if not raw_refresh_token:
                logger.warning(
                    format_log_event(
                        "auth_refresh_failed",
                        request_id=context.request_id,
                        phase=phase,
                        reason="missing_refresh_token",
                        elapsed_ms=_elapsed_ms(started_at),
                    )
                )
                raise AppException("缺少 refresh token", code=4012, status_code=401)

            token_record = await self.refresh_token_repo.get_by_token_hash(hash_refresh_token(raw_refresh_token, settings=self.settings))
            if (
                token_record is None
                or token_record.revoked_at is not None
                or self._as_utc(token_record.expires_at) <= datetime.now(timezone.utc)
            ):
                logger.warning(
                    format_log_event(
                        "auth_refresh_failed",
                        request_id=context.request_id,
                        phase=phase,
                        reason="invalid_refresh_token",
                        elapsed_ms=_elapsed_ms(started_at),
                    )
                )
                raise AppException("refresh token 无效或已过期", code=4013, status_code=401)

            phase = "load_user"
            user = await self.user_repo.get_by_id(token_record.user_id)
            if user is None:
                logger.warning(
                    format_log_event(
                        "auth_refresh_failed",
                        request_id=context.request_id,
                        phase=phase,
                        reason="user_not_found",
                        elapsed_ms=_elapsed_ms(started_at),
                    )
                )
                raise AppException("用户不存在", code=4041, status_code=404)
            self._ensure_user_is_active(user)

            now = datetime.now(timezone.utc)
            next_raw_refresh_token = generate_refresh_token()
            phase = "refresh_token_create"
            replacement = self._build_refresh_token_record(user=user, raw_token=next_raw_refresh_token, context=context, issued_at=now)
            access_token, expires_in = create_access_token(user_id=user.id, settings=self.settings)

            self.refresh_token_repo.add(replacement)
            token_record.revoked_at = now
            token_record.replaced_by_token_id = replacement.id
            phase = "commit"
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            logger.exception(
                format_log_event(
                    "auth_refresh_failed",
                    request_id=context.request_id,
                    phase=phase,
                    elapsed_ms=_elapsed_ms(started_at),
                )
            )
            raise AppException("刷新登录态失败，请稍后重试", code=5003, status_code=500) from exc
        except AppException:
            raise
        except Exception:
            await self.session.rollback()
            logger.exception(
                format_log_event(
                    "auth_refresh_failed",
                    request_id=context.request_id,
                    phase=phase,
                    elapsed_ms=_elapsed_ms(started_at),
                )
            )
            raise
        await self.session.refresh(user)
        logger.info(
            format_log_event(
                "auth_refresh_succeeded",
                request_id=context.request_id,
                user_id=user.id.hex,
                elapsed_ms=_elapsed_ms(started_at),
            )
        )

        return AuthSessionBundle(access_token=access_token, expires_in=expires_in, refresh_token=next_raw_refresh_token, user=user)

    async def logout(self, raw_refresh_token: str | None, *, context: RequestContext) -> bool:
        """撤销当前 refresh token，并尽量保持幂等。"""

        if not raw_refresh_token:
            return True

        token_record = await self.refresh_token_repo.get_by_token_hash(hash_refresh_token(raw_refresh_token, settings=self.settings))
        if token_record is None or token_record.revoked_at is not None:
            return True

        user = await self.user_repo.get_by_id(token_record.user_id)
        token_record.revoked_at = datetime.now(timezone.utc)
        if user is not None:
            self.audit_log_repo.add(
                self._build_audit_log(
                    action=AuditAction.AUTH_LOGOUT.value,
                    user_id=user.id,
                    object_type="user",
                    object_id=user.id,
                    context=context,
                    payload={"email": user.email},
                )
            )
        try:
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise AppException("登出失败，请稍后重试", code=5004, status_code=500) from exc
        return True

    async def get_current_user(self, access_token: str) -> User:
        """解析 access token 并加载当前用户。"""

        try:
            payload = decode_access_token(access_token, settings=self.settings)
        except ValueError as exc:
            raise AppException("登录态无效或已过期", code=4010, status_code=401) from exc

        user = await self.user_repo.get_by_id(payload.user_id)
        if user is None:
            raise AppException("用户不存在", code=4041, status_code=404)
        self._ensure_user_is_active(user)
        return user

    def _build_refresh_token_record(self, *, user: User, raw_token: str, context: RequestContext, issued_at: datetime) -> RefreshToken:
        """构造 refresh_tokens 表记录。"""

        return RefreshToken(
            id=uuid.uuid4(),
            user_id=user.id,
            token_hash=hash_refresh_token(raw_token, settings=self.settings),
            device_id=context.device_id,
            user_agent=context.user_agent,
            ip_address=context.ip_address,
            expires_at=issued_at + timedelta(days=self.settings.auth_refresh_token_expire_days),
        )

    def _build_audit_log(
        self,
        *,
        action: str,
        user_id,
        object_type: str | None,
        object_id,
        context: RequestContext,
        payload: dict[str, object] | None,
    ) -> AuditLog:
        """构造审计日志记录。"""

        return AuditLog(
            id=uuid.uuid4(),
            user_id=user_id,
            action=action,
            object_type=object_type,
            object_id=object_id,
            request_id=context.request_id,
            ip_address=context.ip_address,
            user_agent=context.user_agent,
            payload=payload,
        )

    def _ensure_user_is_active(self, user: User) -> None:
        """限制被禁用和软删除用户继续登录。"""

        if user.deleted_at is not None:
            raise AppException("用户已删除", code=4031, status_code=403)
        if user.status != UserStatus.ACTIVE.value:
            raise AppException("用户状态不可用", code=4032, status_code=403)

    def _as_utc(self, value: datetime) -> datetime:
        """兼容 SQLite 测试场景返回的 naive datetime。"""

        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)


def _elapsed_ms(started_at: float) -> int:
    return int((perf_counter() - started_at) * 1000)
