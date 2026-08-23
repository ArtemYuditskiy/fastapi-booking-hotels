from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.users.models import User


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_email(self, email: str) -> User | None:
        statement = select(User).where(User.email == email)
        return await self._session.scalar(statement)

    async def get_by_id(self, user_id: int) -> User | None:
        return await self._session.get(User, user_id)

    async def add(self, *, email: str, hashed_password: str) -> User:
        user = User(email=email, hashed_password=hashed_password)
        self._session.add(user)
        await self._session.flush()
        await self._session.refresh(user)
        return user
