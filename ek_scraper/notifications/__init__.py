from __future__ import annotations

import typing as ty

if ty.TYPE_CHECKING:
    from ek_scraper.scraper import Result


class SendNotification(ty.Protocol):
    async def __call__(self, results: ty.Sequence[Result], config_dict: dict[str, ty.Any]):
        ...
