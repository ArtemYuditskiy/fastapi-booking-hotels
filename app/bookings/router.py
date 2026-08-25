from typing import Annotated

from fastapi import APIRouter, Query, status

from app.bookings.schemas import BookingCreate, BookingRead
from app.bookings.service import (
    BookingHoldExpiredError,
    BookingNotFoundError,
    BookingService,
    BookingStateConflictError,
    NoAvailabilityError,
    RoomTypeNotFoundError,
)
from app.exceptions import (
    BookingHoldExpiredException,
    BookingNotFoundException,
    BookingStateConflictException,
    NoAvailabilityException,
    RoomTypeNotFoundException,
)
from app.users.dependencies import CurrentUserDependency, SessionDependency

router = APIRouter(prefix="/api/v1/bookings", tags=["Bookings"])


@router.post(
    "",
    response_model=BookingRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a reservation hold",
)
async def create_booking(
    data: BookingCreate,
    current_user: CurrentUserDependency,
    session: SessionDependency,
) -> BookingRead:
    try:
        booking = await BookingService(session).create(
            user_id=current_user.id,
            data=data,
        )
    except RoomTypeNotFoundError as error:
        raise RoomTypeNotFoundException from error
    except NoAvailabilityError as error:
        raise NoAvailabilityException from error
    return BookingRead.from_booking(booking)


@router.get("", response_model=list[BookingRead], summary="List my bookings")
async def list_bookings(
    current_user: CurrentUserDependency,
    session: SessionDependency,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[BookingRead]:
    bookings = await BookingService(session).list(
        user_id=current_user.id,
        limit=limit,
        offset=offset,
    )
    return [BookingRead.from_booking(booking) for booking in bookings]


@router.get("/{booking_id}", response_model=BookingRead, summary="Get my booking")
async def get_booking(
    booking_id: int,
    current_user: CurrentUserDependency,
    session: SessionDependency,
) -> BookingRead:
    try:
        booking = await BookingService(session).get(
            booking_id=booking_id,
            user_id=current_user.id,
        )
    except BookingNotFoundError as error:
        raise BookingNotFoundException from error
    return BookingRead.from_booking(booking)


@router.post(
    "/{booking_id}/confirm",
    response_model=BookingRead,
    summary="Confirm a reservation hold",
)
async def confirm_booking(
    booking_id: int,
    current_user: CurrentUserDependency,
    session: SessionDependency,
) -> BookingRead:
    try:
        booking = await BookingService(session).confirm(
            booking_id=booking_id,
            user_id=current_user.id,
        )
    except BookingNotFoundError as error:
        raise BookingNotFoundException from error
    except BookingHoldExpiredError as error:
        raise BookingHoldExpiredException from error
    except BookingStateConflictError as error:
        raise BookingStateConflictException from error
    return BookingRead.from_booking(booking)


@router.delete(
    "/{booking_id}",
    response_model=BookingRead,
    summary="Cancel my booking",
)
async def cancel_booking(
    booking_id: int,
    current_user: CurrentUserDependency,
    session: SessionDependency,
) -> BookingRead:
    try:
        booking = await BookingService(session).cancel(
            booking_id=booking_id,
            user_id=current_user.id,
        )
    except BookingNotFoundError as error:
        raise BookingNotFoundException from error
    return BookingRead.from_booking(booking)
