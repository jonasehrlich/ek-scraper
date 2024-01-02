from __future__ import annotations

import asyncio
import collections.abc
import logging
import typing as ty

import httpx

from ek_scraper.config import NtfyShConfig

from . import NotificationError

if ty.TYPE_CHECKING:
    from ek_scraper.scraper import Result

BASE_URL = "https://ntfy.sh"

_logger = logging.getLogger(__name__)


async def send_notification(client: httpx.AsyncClient, config: NtfyShConfig, result: Result) -> None:
    """Send a single notification

    :param client: AsyncClient used to send requests
    :param config: Configuration for ntfy.sh
    :param result: Result of the scraper
    """

    params = config.model_dump()
    params["title"] = result.get_title()
    params["message"] = result.get_message()
    params["click"] = result.get_url()

    _logger.info("Send ntfy.sh notification for '%s'", result.get_title())
    resp = await client.post("/", json=params)
    try:
        resp.raise_for_status()
    except Exception as exc:
        raise NotificationError(f"Received error response: {exc}") from exc


async def send_notifications(results: ty.Sequence[Result], config: NtfyShConfig) -> None:
    """Send notifications for all results from the scraper

    :param results: Results from the scraper
    :param config: Configuration for ntfy.sh notifications
    :raises ValueError: Raised if the required configuration parameters were not provided
    """

    async with httpx.AsyncClient(base_url=BASE_URL) as client:
        tasks: list[collections.abc.Awaitable[ty.Any]] = list()
        for result in results:
            if not result.ad_items:
                continue
            tasks.append(send_notification(client, config=config, result=result))

        await asyncio.gather(*tasks)
