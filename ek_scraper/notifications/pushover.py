from __future__ import annotations

import asyncio
import collections.abc
import logging
import typing as ty

import aiohttp

from ek_scraper.config import PushoverConfig

from . import NotificationError

if ty.TYPE_CHECKING:
    from ek_scraper.scraper import Result

BASE_URL = "https://api.pushover.net"

_logger = logging.getLogger(__name__)


async def send_notification(session: aiohttp.ClientSession, config: PushoverConfig, result: Result) -> None:
    """Send a single notification

    :param session: ClientSession to send requests through
    :type session: aiohttp.ClientSession
    :param config: Configuration for pushover
    :type config: PushoverConfig
    :param result: Result of the scraper
    :type result: Result
    """
    params = config.model_dump_api()

    params["title"] = result.get_title()
    params["message"] = result.get_message()
    params["url"] = result.get_url()

    _logger.info("Send Pushover notification for '%s'", result.get_title())
    resp = await session.post("/1/messages.json", params=params)
    try:
        resp.raise_for_status()
    except Exception as exc:
        raise NotificationError(f"Received error response: {exc}") from exc


async def send_notifications(results: ty.Sequence[Result], config: PushoverConfig) -> None:
    """Send notifications for all results from the scraper

    :param results: Results from the scraper
    :param config: Configuration for Pushover notifications
    :raises ValueError: Raised if the required configuration parameters were not provided
    """

    async with aiohttp.ClientSession(BASE_URL) as session:
        tasks: list[collections.abc.Awaitable[ty.Any]] = list()
        for result in results:
            if not result.ad_items:
                continue
            tasks.append(send_notification(session, config=config, result=result))

        await asyncio.gather(*tasks)
