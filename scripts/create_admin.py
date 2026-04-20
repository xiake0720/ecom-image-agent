"""Create a bootstrap user account.

The current v1 schema has no role/permission table, so this script creates a
normal active user intended for initial operations smoke tests.
"""

from __future__ import annotations

import argparse
import asyncio
import getpass
import uuid

from sqlalchemy.exc import IntegrityError

from backend.core.security import hash_password
from backend.db.enums import UserStatus
from backend.db.models.user import User
from backend.db.session import get_async_session_factory
from backend.repositories.db.user_repository import UserRepository


async def create_user(*, email: str, password: str, nickname: str | None, update_password: bool) -> int:
    session_factory = get_async_session_factory()
    async with session_factory() as session:
        repo = UserRepository(session)
        existing = await repo.get_by_email(email)
        if existing is not None:
            if not update_password:
                print(f"User already exists: {email}")
                return 0
            existing.password_hash = hash_password(password)
            existing.nickname = nickname or existing.nickname
            existing.status = UserStatus.ACTIVE.value
            await session.commit()
            print(f"Updated bootstrap user: {email}")
            return 0

        user = User(
            id=uuid.uuid4(),
            email=email,
            password_hash=hash_password(password),
            nickname=nickname or "Bootstrap User",
            status=UserStatus.ACTIVE.value,
            email_verified=True,
        )
        repo.add(user)
        try:
            await session.commit()
        except IntegrityError:
            await session.rollback()
            print(f"User already exists: {email}")
            return 0
        print(f"Created bootstrap user: {email}")
        return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a bootstrap user account.")
    parser.add_argument("--email", required=True, help="User email.")
    parser.add_argument("--nickname", default=None, help="Optional display nickname.")
    parser.add_argument("--password", default=None, help="Password. Omit to enter interactively.")
    parser.add_argument("--update-password", action="store_true", help="Update password if the user already exists.")
    args = parser.parse_args()

    password = args.password or getpass.getpass("Password: ")
    if len(password) < 8:
        print("Password must be at least 8 characters.")
        return 2
    return asyncio.run(
        create_user(
            email=args.email,
            password=password,
            nickname=args.nickname,
            update_password=args.update_password,
        )
    )


if __name__ == "__main__":
    raise SystemExit(main())
