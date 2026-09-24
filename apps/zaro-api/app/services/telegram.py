"""Telegram staff alerts.

Notification is strictly additive and best-effort: a missing/empty token
or chat id disables the feature entirely, and any transport failure is
logged and swallowed so an alert can never break the API response path.
Tokens are read from settings (env) at runtime — never hard-coded.
"""

from __future__ import annotations

import logging

import httpx

from app.core.config import Settings

logger = logging.getLogger(__name__)

BOT_API_BASE = "https://api.telegram.org"
_TRUNCATE = 1000


def format_request_alert(
    *,
    reference: str,
    customer_name: str,
    product_type: str,
    description: str,
    email: str | None,
    phone: str | None,
    wilaya: str | None,
    commune: str | None,
) -> str:
    """Compose the staff HTML message for a new custom request."""
    lines = ["<b>New custom request</b>", f"Ref: <code>{reference}</code>", f"Name: {customer_name}"]
    if email:
        lines.append(f"Email: {email}")
    if phone:
        lines.append(f"Phone: {phone}")
    lines.append(f"Type: {product_type}")
    if wilaya:
        location = f"Location: {wilaya}"
        if commune:
            location += f" · {commune}"
        lines.append(location)
    brief = description.strip()
    if len(brief) > _TRUNCATE:
        brief = brief[:_TRUNCATE].rstrip() + "…"
    lines.append(f"Brief: {brief}")
    return "\n".join(lines)


async def send_alert(settings: Settings, text: str) -> bool:
    """Send a message; return False (and stay silent) when disabled or on failure."""
    token = settings.telegram_bot_token.strip()
    chat_id = settings.telegram_chat_id.strip()
    if not token or not chat_id:
        return False

    url = f"{BOT_API_BASE}/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    try:
        async with httpx.AsyncClient(timeout=settings.telegram_alert_timeout_seconds) as client:
            response = await client.post(url, json=payload)
        if response.status_code != 200:
            logger.warning("Telegram alert rejected: HTTP %s (%s)", response.status_code, response.text[:200])
            return False
        return True
    except httpx.HTTPError:
        logger.warning("Telegram alert transport failure", exc_info=True)
        return False
