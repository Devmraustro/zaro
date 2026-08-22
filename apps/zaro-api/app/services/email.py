"""Email delivery abstraction.

Phase 1.3 ships a development-safe sender that logs messages instead of
delivering them. A production SMTP/provider implementation plugs in later by
implementing ``EmailSender``; call sites never change.
"""

from dataclasses import dataclass
from typing import Protocol

from app.core.logging import get_logger

logger = get_logger("app.services.email")


@dataclass(frozen=True)
class EmailMessage:
    to_address: str
    subject: str
    body: str


class EmailSender(Protocol):
    async def send(self, message: EmailMessage) -> None: ...


class ConsoleEmailSender:
    """Logs delivery metadata only — never the body.

    Password-reset emails embed single-use tokens; logging bodies would leak
    them into log aggregation (Phase 1.4 finding C1).
    """

    async def send(self, message: EmailMessage) -> None:
        logger.info(
            "email_console_delivery",
            to=message.to_address,
            subject=message.subject,
            body_length=len(message.body),
        )


def get_email_sender() -> EmailSender:
    # Production provider selection arrives with the notifications phase;
    # until then every environment uses the console sender.
    return ConsoleEmailSender()
