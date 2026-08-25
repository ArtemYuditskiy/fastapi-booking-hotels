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
            existing_user = await self._repository.get_by_email(email)
            if existing_user is not None:
                raise UserAlreadyExistsError

            user = await self._repository.add(
                email=email,
                hashed_password=hash_password(password),
            )
            await self._session.commit()
            return user
        except IntegrityError as error:
            await self._session.rollback()
            raise UserAlreadyExistsError from error
        except Exception:
            await self._session.rollback()
            raise

    async def authenticate(self, *, email: str, password: str) -> User | None:
        user = await self._repository.get_by_email(email)
        if user is None or not verify_password(password, user.hashed_password):
            return None
        return user
