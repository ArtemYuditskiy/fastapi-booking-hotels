import pytest
from pydantic import ValidationError

from app.config import DEVELOPMENT_JWT_SECRET, Settings


def test_jwt_secret_must_contain_at_least_32_characters() -> None:
    with pytest.raises(ValidationError, match="at least 32 characters"):
        Settings(JWT_SECRET="too-short")


def test_production_rejects_the_development_jwt_secret() -> None:
    with pytest.raises(ValidationError, match="must be changed in production"):
        Settings(MODE="PROD", JWT_SECRET=DEVELOPMENT_JWT_SECRET)


def test_production_accepts_a_custom_jwt_secret() -> None:
    configured = Settings(MODE="PROD", JWT_SECRET="x" * 32)

    assert configured.JWT_SECRET == "x" * 32
