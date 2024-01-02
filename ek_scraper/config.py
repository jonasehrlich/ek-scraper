from __future__ import annotations

import pathlib
import re
import typing as ty
import enum
import pydantic
import yaml

NTFY_SH_PRIORITIES = ty.Literal[5, 4, 3, 2, 1]


class ConfigFileFormat(enum.StrEnum):
    """Format of the configuration file"""

    YAML = enum.auto()
    JSON = enum.auto()

    @classmethod
    def from_path(cls, path: pathlib.Path) -> ConfigFileFormat:
        try:
            return ConfigFileFormat(path.suffix[1:])
        except ValueError:
            raise ValueError(f"asdInvalid configuration file format: {format}")


class SearchConfig(pydantic.BaseModel):
    """Configuration of a search"""

    name: str
    url: str
    recursive: bool = True


class FilterConfig(pydantic.BaseModel):
    """Configuration of filters"""

    exclude_topads: bool = True
    exclude_patterns: list[re.Pattern[str]] = pydantic.Field(default_factory=list)

    @pydantic.field_validator("exclude_patterns")
    @classmethod
    def validate_exclude_patterns(
        cls, exclude_patterns: list[str], _info: pydantic.ValidationInfo
    ) -> list[re.Pattern[str]]:
        """Validate the exclude patterns by compiling them

        :param exclude_patterns: List of exclude patterns as strings
        :param _info: Validation info object
        :return: List of compiled patterns
        """
        return [re.compile(pattern, re.IGNORECASE) for pattern in exclude_patterns]

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
    topic: str = "<my-topic>"
    priority: NTFY_SH_PRIORITIES = 3


class PushoverConfig(pydantic.BaseModel):
    token: str = "<my-token>"
    user: str = "<my-user>"
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

    @classmethod
    def from_file(cls, path: pathlib.Path) -> ty.Self:
        """
        Create a config object from a path

        :param path: Path to read the config from
        :return: Validated config object
        """
        format = ConfigFileFormat.from_path(path)
        if format == ConfigFileFormat.JSON:
            return cls.model_validate_json(path.read_bytes())
        elif format == ConfigFileFormat.YAML:
            with path.open() as f:
                data = yaml.safe_load(f)
                return cls(**data)
        else:
            raise ValueError(f"Invalid configuration file format: {format}")

    def to_file(self, path: pathlib.Path) -> None:
        """
        Dump the configuration to a file

        :param path: Path to write the config file to
        :param format: Format of the configuration file, defaults to ConfigFileFormat.YAML
        :raises ValueError: Raised for invalid file format
        """
        format = ConfigFileFormat.from_path(path)
        if format == ConfigFileFormat.JSON:
            path.write_text(self.model_dump_json(indent=2, by_alias=True, exclude_none=True))
        elif format == ConfigFileFormat.YAML:
            data = self.model_dump()
            with path.open("w") as f:
                yaml.safe_dump(data, f)
        else:
            raise ValueError(f"Invalid configuration file format: {format}")
