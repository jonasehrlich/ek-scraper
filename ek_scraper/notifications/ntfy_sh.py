from __future__ import annotations

import asyncio
import collections.abc
import logging
import typing as ty

import aiohttp

from ek_scraper.config import NtfyShConfig
from ek_scraper.data_store import AdItem

from . import NotificationError

if ty.TYPE_CHECKING:
    from ek_scraper.scraper import Result

BASE_URL = "https://ntfy.sh"

_logger = logging.getLogger(__name__)


async def send_ad_notification(
    session: aiohttp.ClientSession, config: NtfyShConfig, search_name: str, ad: AdItem
) -> None:
    """Send a notification for a single ad item"""
    params = config.model_dump()
    params["title"] = f"{search_name}: {ad.price}"

    details = []
    if ad.mileage:
        details.append(ad.mileage)
    if ad.registration:
        details.append(ad.registration)
    if ad.location:
        details.append(ad.location)

    params["message"] = f"{ad.title}\n{' | '.join(details)}" if details else ad.title
    params["click"] = ad.url

    _logger.info("Send ntfy.sh notification for ad '%s'", ad.title)
    resp = await session.post("/", json=params)
    try:
        resp.raise_for_status()
    except Exception as exc:
        raise NotificationError(f"Received error response: {exc}") from exc


async def send_notifications(results: ty.Sequence[Result], config: NtfyShConfig) -> None:
    """Send notifications for all results from the scraper

    :param results: Results from the scraper
    :type results: ty.Sequence[Result]
    :param config: Configuration for ntfy.sh notifications
    :raises ValueError: Raised if the required configuration parameters were not provided
    """

    async with aiohttp.ClientSession(BASE_URL) as session:
        tasks: list[collections.abc.Awaitable[ty.Any]] = list()
        for result in results:
            for ad in result.ad_items:
                tasks.append(send_ad_notification(session, config=config, search_name=result.get_title(), ad=ad))

        await asyncio.gather(*tasks)
