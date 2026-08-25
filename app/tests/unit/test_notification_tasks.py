import pytest

from app.config import settings
from app.notifications import tasks
from app.notifications.delivery import DeliveryOutcome, DeliveryResult
from app.tasks.celery import celery


def test_beat_schedule_contains_expiration_and_notification_dispatch() -> None:
    schedule = celery.conf.beat_schedule

    assert schedule["expire-booking-holds"] == {
        "task": "bookings.expire_holds",
        "schedule": float(settings.CELERY_BEAT_INTERVAL_SECONDS),
    }
    assert schedule["dispatch-pending-notifications"] == {
        "task": "notifications.dispatch_pending",
        "schedule": float(settings.NOTIFICATION_DISPATCH_INTERVAL_SECONDS),
    }


def test_dispatcher_publishes_notification_ids_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    published_ids: list[int] = []
    monkeypatch.setattr(
        tasks,
        "run_database_task",
        lambda _operation: [11, 12],
    )
    monkeypatch.setattr(tasks.send_notification, "delay", published_ids.append)

    dispatched_count = tasks.dispatch_pending_notifications.run()

    assert dispatched_count == 2
    assert published_ids == [11, 12]


def test_send_task_uses_celery_retry_countdown(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class RetryRequested(Exception):
        pass

    retry_arguments: dict[str, int | None] = {}

    def request_retry(*, countdown: int | None, max_retries: int | None) -> Exception:
        retry_arguments.update(
            countdown=countdown,
            max_retries=max_retries,
        )
        return RetryRequested()

    monkeypatch.setattr(
        tasks,
        "run_database_task",
        lambda _operation: DeliveryResult(DeliveryOutcome.RETRY, 30),
    )
    monkeypatch.setattr(tasks.send_notification, "retry", request_retry)

    with pytest.raises(RetryRequested):
        tasks.send_notification.run(42)

    assert retry_arguments == {"countdown": 30, "max_retries": None}
