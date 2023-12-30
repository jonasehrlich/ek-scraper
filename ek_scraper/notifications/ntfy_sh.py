from __future__ import annotations

import asyncio
import dataclasses
import logging
import typing as ty

import aiohttp

if ty.TYPE_CHECKING:
    from ek_scraper import Result

BASE_URL = "https://ntfy.sh"

_logger = logging.getLogger(__name__)

PRIORITIES = ty.Literal[5, 4, 3, 2, 1, "max", "urgent", "high", "default", "low", "min"]


@dataclasses.dataclass(frozen=True)
class NtfyShConfig:
    topic: str
    priority: PRIORITIES = "urgent"

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


async def send_notification(session: aiohttp.ClientSession, config: NtfyShConfig, result: Result):
    """Send a single notification

    :param session: ClientSession to send requests through
    :type session: aiohttp.ClientSession
    :param config: Configuration for ntfy.sh
    :type config: NtfyShConfig
    :param result: Result of the scraper
    :type result: Result
    """
    plural = "" if len(result.aditems) == 1 else "s"
    message = f"Found {len(result.aditems)} new ad{plural} for '{result.search_config.name}'"

    params = dataclasses.asdict(config)
    params["message"] = message
    params["click"] = result.search_config.url

    resp = await session.post("", data=message)
    resp.raise_for_status()
    _logger.debug("Response %s", resp.json())


async def send_notifications(results: ty.Sequence[Result], config_dict: dict[str, ty.Any]):
    """Send notifications for all results from the scraper

    :param results: Results from the scraper
    :type results: ty.Sequence[Result]
    :param config_dict: Configuration for the notification
    :type config_dict: dict
    :raises ValueError: Raised if the required configuration parameters were not provided
    """
    try:
        config = NtfyShConfig(**config_dict)
    except TypeError:
        raise ValueError(f"Could not create NtfyShConfig from {config_dict}") from None

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
