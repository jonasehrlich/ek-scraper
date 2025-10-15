import re
import typing as ty

import pydantic

NTFY_SH_PRIORITIES = ty.Literal[5, 4, 3, 2, 1]


class SearchConfig(pydantic.BaseModel):
    """Configuration of a search"""

    name: str
    url: str
    recursive: bool = True


class FilterConfig(pydantic.BaseModel):
    """Configuration of filters"""

    exclude_topads: bool = True
    exclude_patterns: list[re.Pattern[str]] = pydantic.Field(default_factory=list)

    @pydantic.field_serializer("exclude_patterns")
    def serialize_exclude_patterns(
        self, exclude_patterns: list[re.Pattern[str]], _info: pydantic.FieldSerializationInfo
    ) -> list[str]:
        """Serialize the compiled exclude patterns to a list of strings

        :param exclude_patterns: List of compiled patterns
        :param _info: Serialization info object
        :return: List of patterns as strings
        """
        return [p.pattern for p in exclude_patterns]


class NtfyShConfig(pydantic.BaseModel):
    topic: str
    priority: NTFY_SH_PRIORITIES = 3


class PushoverConfig(pydantic.BaseModel):
    token: str
    user: str
    device: list[str] = pydantic.Field(default_factory=list)

    def model_dump_api(self) -> dict[str, ty.Any]:
        data = self.model_dump()
        if self.device:
            data["device"] = ",".join(self.device)
        return data


class NotificationsConfig(pydantic.BaseModel):
    """Configuration for notifications"""

    pushover: PushoverConfig | None = None
    ntfy_sh: NtfyShConfig | None = pydantic.Field(default=None, alias="ntfy.sh")


class Config(pydantic.BaseModel):
    """Overall configuration object"""

    filter: FilterConfig = pydantic.Field(default_factory=FilterConfig)
    notifications: NotificationsConfig = pydantic.Field(default_factory=NotificationsConfig)
    searches: list[SearchConfig] = pydantic.Field(default_factory=list)
