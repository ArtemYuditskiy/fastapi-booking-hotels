import asyncio
import smtplib
from dataclasses import dataclass
from email.message import EmailMessage
from typing import Protocol


class PermanentEmailDeliveryError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class OutgoingEmail:
    recipient: str
    sender: str
    subject: str
    body: str


class EmailSender(Protocol):
    async def send(self, message: OutgoingEmail) -> None: ...


class SMTPEmailSender:
    def __init__(self, *, host: str, port: int, timeout: float) -> None:
        self._host = host
        self._port = port
        self._timeout = timeout

    async def send(self, message: OutgoingEmail) -> None:
        await asyncio.to_thread(self._send_sync, message)

    def _send_sync(self, outgoing: OutgoingEmail) -> None:
        message = EmailMessage()
        message["From"] = outgoing.sender
        message["To"] = outgoing.recipient
        message["Subject"] = outgoing.subject
        message.set_content(outgoing.body)

        try:
            with smtplib.SMTP(
                host=self._host,
                port=self._port,
                timeout=self._timeout,
            ) as client:
                client.send_message(message)
        except smtplib.SMTPRecipientsRefused as error:
            raise PermanentEmailDeliveryError("SMTP rejected the recipient") from error
        except smtplib.SMTPResponseException as error:
            if 500 <= error.smtp_code < 600:
                raise PermanentEmailDeliveryError(
                    f"SMTP rejected the message with status {error.smtp_code}"
                ) from error
            raise
