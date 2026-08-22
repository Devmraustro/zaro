"""Owner bootstrap script.

Creates the initial OWNER account for a fresh ZARO installation.

Usage:
    uv run python -m app.scripts.bootstrap_owner

Requirements:
    - ZARO_DATABASE_URL must be set
    - ZARO_SECRET_KEY must be set
    - Must be run interactively (prompts for email and password)

Security:
    - No hardcoded credentials
    - No public API endpoint
    - Password prompted interactively
    - Cannot create duplicate OWNER accounts
"""

import asyncio
import getpass
import sys
import uuid
from datetime import UTC, datetime

from sqlalchemy import select

from app.core.config import Settings
from app.core.security import hash_password
from app.db.session import create_session_factory, dispose_db_engines
from app.models.enums import Role
from app.models.user import User


async def _bootstrap_owner() -> None:
    settings = Settings(_env_file=None)

    print("ZARO Owner Bootstrap")
    print("====================")
    print()

    email = input("Owner email: ").strip()
    if not email:
        print("Error: email is required")
        sys.exit(1)

    password = getpass.getpass("Owner password: ")
    if len(password) < 8:
        print("Error: password must be at least 8 characters")
        sys.exit(1)

    confirm = getpass.getpass("Confirm password: ")
    if password != confirm:
        print("Error: passwords do not match")
        sys.exit(1)

    full_name = input("Full name: ").strip()
    if not full_name:
        print("Error: full name is required")
        sys.exit(1)

    factory = create_session_factory(settings)
    try:
        async with factory() as db:
            existing = await db.execute(select(User).where(User.email == email))
            if existing.scalar_one_or_none() is not None:
                print(f"Error: user with email {email} already exists")
                sys.exit(1)

            owner_count = await db.execute(select(User).where(User.role == Role.OWNER))
            if owner_count.scalar_one_or_none() is not None:
                print("Error: an OWNER account already exists")
                sys.exit(1)

            user = User(
                id=uuid.uuid4(),
                email=email,
                hashed_password=hash_password(password),
                full_name=full_name,
                role=Role.OWNER,
                is_active=True,
                last_login_at=None,
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )
            db.add(user)
            await db.commit()

            print()
            print(f"OWNER account created: {email}")
            print(f"User ID: {user.id}")
            print("You can now log in via POST /api/v1/auth/login")
    finally:
        await dispose_db_engines()


def main() -> None:
    asyncio.run(_bootstrap_owner())


if __name__ == "__main__":
    main()
