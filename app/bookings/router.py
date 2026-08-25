from fastapi import APIRouter, status

from app.bookings.schemas import BookingCreate, BookingRead
from app.bookings.service import (
    BookingService,
    NoAvailabilityError,
    RoomTypeNotFoundError,
)
from app.exceptions import NoAvailabilityException, RoomTypeNotFoundException
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
    return BookingRead.model_validate(booking)
