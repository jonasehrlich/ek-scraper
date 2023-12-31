from __future__ import annotations

import asyncio
import dataclasses
import logging
import typing as ty

import aiohttp

from . import NotificationError

if ty.TYPE_CHECKING:
    from ek_scraper import Result

BASE_URL = "https://api.pushover.net"

_logger = logging.getLogger(__name__)


@dataclasses.dataclass(frozen=True)
class PushoverConfig:
    token: str
    user: str
    device: list[str] = dataclasses.field(default_factory=list)

    def to_params(self) -> dict[str, str]:
        params = dict()
        for field in dataclasses.fields(self):
            value = getattr(self, field.name)
            if not value:
                continue
            if isinstance(value, list):
                value = ",".join(value)
            params[field.name] = value
        return params

    @classmethod
    def to_default_dict(cls):
        data = dict()
        for field in dataclasses.fields(cls):
            if field.default is not dataclasses.MISSING:
                value = field.default
            elif field.default_factory is not dataclasses.MISSING:
                value = field.default_factory()
            else:
                value = f"<my-{field.name}>"
            data[field.name] = value
        return data


async def send_notification(session: aiohttp.ClientSession, config: PushoverConfig, result: Result):
    """Send a single notification

    :param session: ClientSession to send requests through
    :type session: aiohttp.ClientSession
    :param config: Configuration for pushover
    :type config: PushoverConfig
    :param result: Result of the scraper
    :type result: Result
    """
    params = config.to_params()

    params["title"] = result.get_title()
    params["message"] = result.get_message()
    params["url"] = result.get_url()

    resp = await session.post("/1/messages.json", params=params)
    try:
        resp.raise_for_status()
    except Exception as exc:
        raise NotificationError(f"Received error response: {exc}") from exc


async def send_notifications(results: ty.Sequence[Result], config_dict: dict[str, ty.Any]):
    """Send notifications for all results from the scraper

    :param results: Results from the scraper
    :type results: ty.Sequence[Result]
    :param config_dict: Configuration for the notification
    :type config_dict: dict
    :raises ValueError: Raised if the required configuration parameters were not provided
    """
    try:
        config = PushoverConfig(**config_dict)
    except TypeError:
        raise ValueError(f"Could not create PushoverConfig from {config_dict}") from None

    async with aiohttp.ClientSession(BASE_URL) as session:
        tasks = list()
        for result in results:
            if not result.aditems:
                _logger.info("")
                continue
            tasks.append(
                send_notification(
                    session,
                    config=config,
                    result=result,
                )
            )

        await asyncio.gather(*tasks)
