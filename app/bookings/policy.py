from datetime import date, timedelta

BOOKING_HOLD_DURATION = timedelta(minutes=15)
MAX_STAY_NIGHTS = 30


def validate_stay_period(date_from: date, date_to: date) -> None:
    if date_from < date.today():
        raise ValueError("date_from must be today or later")
    if date_to <= date_from:
        raise ValueError("date_to must be later than date_from")
    if (date_to - date_from).days > MAX_STAY_NIGHTS:
        raise ValueError(f"A stay cannot exceed {MAX_STAY_NIGHTS} nights")
