import smtplib
from email.message import EmailMessage

import pytest

from app.notifications.mailer import (
    OutgoingEmail,
    PermanentEmailDeliveryError,
    SMTPEmailSender,
)


class FakeSMTP:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.messages: list[EmailMessage] = []

    def __enter__(self) -> "FakeSMTP":
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def send_message(self, message: EmailMessage) -> None:
        if self.error is not None:
            raise self.error
        self.messages.append(message)


def outgoing_email() -> OutgoingEmail:
    return OutgoingEmail(
        recipient="traveler@example.com",
        sender="bookings@example.test",
        subject="Booking confirmed",
        body="Your booking is confirmed.",
    )


async def test_smtp_sender_builds_plain_text_message(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    smtp = FakeSMTP()
    monkeypatch.setattr(smtplib, "SMTP", lambda **_options: smtp)

    await SMTPEmailSender(host="localhost", port=1025, timeout=1).send(outgoing_email())

    assert len(smtp.messages) == 1
    message = smtp.messages[0]
    assert message["From"] == "bookings@example.test"
    assert message["To"] == "traveler@example.com"
    assert message["Subject"] == "Booking confirmed"
    assert message.get_content().strip() == "Your booking is confirmed."


@pytest.mark.parametrize(
    "smtp_error",
    [
        smtplib.SMTPRecipientsRefused({"traveler@example.com": (550, b"rejected")}),
        smtplib.SMTPResponseException(550, b"message rejected"),
    ],
)
async def test_permanent_smtp_rejection_is_classified_without_retry(
    monkeypatch: pytest.MonkeyPatch,
    smtp_error: Exception,
) -> None:
    monkeypatch.setattr(
        smtplib,
        "SMTP",
        lambda **_options: FakeSMTP(smtp_error),
    )

    with pytest.raises(PermanentEmailDeliveryError):
        await SMTPEmailSender(host="localhost", port=1025, timeout=1).send(
            outgoing_email()
        )


async def test_temporary_smtp_response_is_preserved_for_retry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    smtp_error = smtplib.SMTPResponseException(421, b"try again later")
    monkeypatch.setattr(
        smtplib,
        "SMTP",
        lambda **_options: FakeSMTP(smtp_error),
    )

    with pytest.raises(smtplib.SMTPResponseException) as raised:
        await SMTPEmailSender(host="localhost", port=1025, timeout=1).send(
            outgoing_email()
        )

    assert raised.value.smtp_code == 421
