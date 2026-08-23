from typing import Annotated

from fastapi import APIRouter, Depends, status
from fastapi.security import OAuth2PasswordRequestForm

from app.exceptions import InvalidCredentialsException, UserAlreadyExistsException
from app.users.dependencies import CurrentUserDependency, SessionDependency
from app.users.schemas import Token, UserCreate, UserRead
from app.users.security import create_access_token
from app.users.service import UserAlreadyExistsError, UserService

router = APIRouter(prefix="/api/v1/auth", tags=["Authentication"])


@router.post(
    "/register",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
    summary="Register a user",
)
async def register_user(
    user_data: UserCreate,
    session: SessionDependency,
) -> UserRead:
    try:
        user = await UserService(session).register(
            email=str(user_data.email).lower(),
            password=user_data.password,
        )
    except UserAlreadyExistsError as error:
        raise UserAlreadyExistsException from error
    return UserRead.model_validate(user)


@router.post("/token", response_model=Token, summary="Create an access token")
async def create_token(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    session: SessionDependency,
) -> Token:
    user = await UserService(session).authenticate(
        email=form_data.username.lower(),
        password=form_data.password,
    )
    if user is None:
        raise InvalidCredentialsException
    return Token(access_token=create_access_token(user.id))


@router.get("/me", response_model=UserRead, summary="Get the current user")
async def get_current_user(current_user: CurrentUserDependency) -> UserRead:
    return UserRead.model_validate(current_user)
