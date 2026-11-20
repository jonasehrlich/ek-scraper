from __future__ import annotations

import asyncio
import collections.abc
import logging
import typing as ty

import aiohttp

from ek_scraper.config import TelegramConfig

from . import NotificationError

if ty.TYPE_CHECKING:
    from ek_scraper.scraper import Result

BASE_URL = "https://api.telegram.org"

_logger = logging.getLogger(__name__)


async def send_notification(
    session: aiohttp.ClientSession,
    config: TelegramConfig,
    result: Result,
) -> None:
    """Send a single Telegram notification."""

    url = f"{BASE_URL}/bot{config.bot_token}/sendMessage"

    payload = {
        "chat_id": config.chat_id,
        "text": (
            f"{result.get_title()}\n\n"
            f"{result.get_message()}\n\n"
            f"{result.get_url()}"
        ),
        "disable_web_page_preview": False,
    }

    _logger.info(
        "Send Telegram notification for '%s'",
        result.get_title(),
    )

    try:
        async with session.post(url, json=payload) as resp:
            resp.raise_for_status()
            data = await resp.json()

            if not data.get("ok", False):
                raise NotificationError(
                    f"Telegram API error: {data.get('description', 'Unknown error')}"
                )
    except NotificationError:
        raise
    except (aiohttp.ClientError, TimeoutError, ValueError) as exc:
        raise NotificationError(
            f"Failed to send Telegram notification: {exc}"
        ) from exc


async def send_notifications(
    results: ty.Sequence[Result],
    config: TelegramConfig,
) -> None:
    """Send Telegram notifications for all matching scraper results."""

    async with aiohttp.ClientSession() as session:
        tasks: list[collections.abc.Awaitable[None]] = [
            send_notification(session, config, result)
            for result in results
            if result.ad_items
        ]

        await asyncio.gather(*tasks)
