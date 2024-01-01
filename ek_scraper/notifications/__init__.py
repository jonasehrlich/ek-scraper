from __future__ import annotations

import typing as ty

if ty.TYPE_CHECKING:
    from ek_scraper.scraper import Result

T = ty.TypeVar("T")


class SendNotifications(ty.Protocol):
    async def __call__(self, results: ty.Sequence[Result], config: ty.Any) -> None:
        """
        Interface of the send notifications callback

        :param results: Sequence of results
        :param config: Configuration for the callback
        """
        ...


class ConfiguredSendNotifications(ty.Protocol):
    async def __call__(self, results: ty.Sequence[Result]) -> None:
        """
        Interface of the send notifications callback without the config. The config could be added
        using :func:`functools.partial`.

        :param results: Sequence of results
        """
        ...


class NotificationError(RuntimeError):
    """Raised for failed notification attempts"""
