"""Unit tests for the Telegram staff alert service (no network required)."""

import pytest

from app.core.config import Settings
from app.services.telegram import format_request_alert, send_alert


def _settings(**overrides) -> Settings:
    defaults = {"telegram_bot_token": "", "telegram_chat_id": ""}
    defaults.update(overrides)
    return Settings(**defaults)


def test_format_request_alert_includes_key_details():
    text = format_request_alert(
        reference="CR-2026-0001",
        customer_name="Yasmine Haddad",
        product_type="dining_table",
        description="Large oak dining table for 8 people",
        email="yasmine@example.com",
        phone="0661223344",
        wilaya="16",
        commune="El Biar",
    )
    assert "CR-2026-0001" in text
    assert "Yasmine Haddad" in text
    assert "dining_table" in text
    assert "yasmine@example.com" in text
    assert "0661223344" in text
    assert "16" in text and "El Biar" in text
    assert "Large oak dining table" in text


def test_format_request_alert_omits_missing_contact_and_location():
    text = format_request_alert(
        reference="CR-2026-0002",
        customer_name="Lina M.",
        product_type="desk",
        description="Standing desk",
        email=None,
        phone=None,
        wilaya=None,
        commune=None,
    )
    assert "Email:" not in text
    assert "Phone:" not in text
    assert "Location:" not in text


def test_format_request_alert_truncates_long_brief():
    text = format_request_alert(
        reference="CR-2026-0003",
        customer_name="A B",
        product_type="other",
        description="x" * 5000,
        email=None,
        phone=None,
        wilaya=None,
        commune=None,
    )
    assert len(text) < 1200
    assert text.rstrip().endswith("…")


@pytest.mark.anyio
async def test_send_alert_disabled_without_token_or_chat():
    # No token, no chat -> must never reach the network.
    assert await send_alert(_settings(), "hello") is False
    assert await send_alert(_settings(telegram_bot_token="123:abc"), "hello") is False
    assert await send_alert(_settings(telegram_chat_id="42"), "hello") is False
