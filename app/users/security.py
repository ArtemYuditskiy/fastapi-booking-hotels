from datetime import UTC, datetime, timedelta

import jwt
from jwt import InvalidTokenError as PyJWTInvalidTokenError
from pwdlib import PasswordHash

from app.config import settings

password_hash = PasswordHash.recommended()


class InvalidAccessTokenError(ValueError):
    pass


def hash_password(password: str) -> str:
    return password_hash.hash(password)


def verify_password(password: str, hashed_password: str) -> bool:
    return password_hash.verify(password, hashed_password)


def create_access_token(user_id: int) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "iat": now,
        "exp": now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    }
    return jwt.encode(
        payload,
        settings.JWT_SECRET,
        algorithm=settings.JWT_ALGORITHM,
    )


def decode_access_token(token: str) -> int:
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET,
            algorithms=[settings.JWT_ALGORITHM],
        )
        subject = payload.get("sub")
        if not isinstance(subject, str):
            raise InvalidAccessTokenError
        return int(subject)
    except (PyJWTInvalidTokenError, TypeError, ValueError) as error:
        raise InvalidAccessTokenError from error
