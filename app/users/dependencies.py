from typing import Annotated

from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.exceptions import InvalidCredentialsException
from app.users.models import User
from app.users.repository import UserRepository
from app.users.security import InvalidAccessTokenError, decode_access_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token")
SessionDependency = Annotated[AsyncSession, Depends(get_session)]


async def get_current_user(
    session: SessionDependency,
    token: Annotated[str, Depends(oauth2_scheme)],
) -> User:
    try:
        user_id = decode_access_token(token)
    except InvalidAccessTokenError as error:
        raise InvalidCredentialsException from error

    user = await UserRepository(session).get_by_id(user_id)
    if user is None:
        raise InvalidCredentialsException
    return user


CurrentUserDependency = Annotated[User, Depends(get_current_user)]
