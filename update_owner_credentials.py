#!/usr/bin/env python3
"""Скрипт для обновления email и пароля владельца (owner)."""

import asyncio
import secrets
import string
import sys

from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from app.models.user import User
from app.models.enums import UserRole
from app.core.security import get_password_hash
from app.core.config import settings


def generate_strong_password(length: int = 16) -> str:
    """Генерирует сильный пароль."""
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    password = ''.join(secrets.choice(alphabet) for _ in range(length))
    return password


async def update_owner_email_and_password():
    """Обновляет email и пароль владельца."""
    # Создаем подключение к базе данных
    engine = create_async_engine(settings.database_url, echo=True)
    async_session_maker = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session_maker() as session:
        # Находим пользователя с ролью OWNER
        result = await session.execute(select(User).where(User.role == UserRole.OWNER))
        owner = result.scalar_one_or_none()

        if not owner:
            print("❌ Пользователь с ролью OWNER не найден!")
            sys.exit(1)

        print(f"✅ Найден владелец: ID={owner.id}, Имя={owner.name}, Текущий email={owner.email}")

        # Генерируем новый пароль
        new_password = generate_strong_password(16)
        print(f"🔑 Новый пароль: {new_password}")

        # Хешируем пароль
        password_hash = get_password_hash(new_password)
        print(f"🔒 Хеш пароля: {password_hash}")

        # Обновляем email и пароль
        new_email = "olimsafaralizoda0@gmail.com"
        owner.email = new_email
        owner.password_hash = password_hash

        await session.commit()

        print(f"✅ Успешно обновлено!")
        print(f"📧 Email: {new_email}")
        print(f"🔑 Пароль: {new_password}")
        print(f"⚠️  Сохраните этот пароль, он будет показан только один раз!")


if __name__ == "__main__":
    asyncio.run(update_owner_email_and_password())
