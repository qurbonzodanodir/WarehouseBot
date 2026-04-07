import asyncio
import sys
import os

# Allow imports from project root
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.database import async_session_factory
from sqlalchemy import select
from app.models.user import User
from app.models.enums import UserRole
from app.core.security import get_password_hash

async def main():
    email = os.getenv("ADMIN_EMAIL")
    password = os.getenv("ADMIN_PASSWORD")
    if not email or not password:
        raise RuntimeError("Set ADMIN_EMAIL and ADMIN_PASSWORD environment variables")
    
    async with async_session_factory() as session:
        # Check if user already exists
        result = await session.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()
        
        if user:
            print(f"Updating existing user with email {email}")
            user.password_hash = get_password_hash(password)
            user.role = UserRole.OWNER
        else:
            print(f"Creating new admin user {email}")
            # Try to find user by telegram_id representing owner just in case
            owner_res = await session.execute(select(User).where(User.role == UserRole.OWNER).limit(1))
            owner = owner_res.scalar_one_or_none()
            if owner and not owner.email:
                print(f"Found existing owner {owner.name}, updating email and password")
                owner.email = email
                owner.password_hash = get_password_hash(password)
            else:
                new_admin = User(
                    name="Admin",
                    email=email,
                    password_hash=get_password_hash(password),
                    role=UserRole.OWNER,
                    telegram_id=None,
                    language_code="ru"
                )
                session.add(new_admin)
        
        await session.commit()
        print(f"Done! Admin created/updated: {email}")

if __name__ == "__main__":
    asyncio.run(main())
