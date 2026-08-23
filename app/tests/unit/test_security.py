import pytest

from app.users.security import (
    InvalidAccessTokenError,
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


def test_password_is_hashed_and_verified() -> None:
    password = "correct-horse-battery-staple"

    hashed_password = hash_password(password)

    assert hashed_password != password
    assert verify_password(password, hashed_password)
    assert not verify_password("wrong-password", hashed_password)


def test_access_token_round_trip() -> None:
    token = create_access_token(user_id=42)

    assert decode_access_token(token) == 42


def test_invalid_access_token_is_rejected() -> None:
    with pytest.raises(InvalidAccessTokenError):
        decode_access_token("not-a-jwt")
