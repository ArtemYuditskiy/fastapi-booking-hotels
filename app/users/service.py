from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.users.models import User
from app.users.repository import UserRepository
from app.users.security import hash_password, verify_password


class UserAlreadyExistsError(ValueError):
    pass


class UserService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repository = UserRepository(session)

    async def register(self, *, email: str, password: str) -> User:
        try:
            async with self._session.begin():
                existing_user = await self._repository.get_by_email(email)
                if existing_user is not None:
                    raise UserAlreadyExistsError

                return await self._repository.add(
                    email=email,
                    hashed_password=hash_password(password),
                )
        except IntegrityError as error:
            raise UserAlreadyExistsError from error

    async def authenticate(self, *, email: str, password: str) -> User | None:
        user = await self._repository.get_by_email(email)
        if user is None or not verify_password(password, user.hashed_password):
            return None
        return user
