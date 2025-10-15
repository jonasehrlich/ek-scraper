import argparse
import asyncio
import collections.abc
import contextlib
import functools
import inspect
import logging
import pathlib
import sys
import tempfile
import textwrap
import typing as ty

from ek_scraper import __version__
from ek_scraper.config import Config, NotificationsConfig, SearchConfig
from ek_scraper.data_store import DataStore
from ek_scraper.error import UnexpectedHTMLResponse
from ek_scraper.notifications import ConfiguredSendNotifications, SendNotifications, ntfy_sh, pushover
from ek_scraper.scraper import Result, get_filtered_search_result, mark_ad_items_as_non_pruneable

_logger = logging.getLogger(__name__.split(".", 1)[0])


NOTIFICATION_CALLBACKS: dict[str, SendNotifications] = {
    "pushover": pushover.send_notifications,
    "ntfy.sh": ntfy_sh.send_notifications,
}

TEMP_DATA_STORE_SENTINEL = object()
DEFAULT_CONFIG = Config(
    searches=[
        SearchConfig(
            name="Wohnungen in Hamburg Altona", url="https://www.kleinanzeigen.de/s-wohnung-mieten/altona/c203l9497"
        )
    ]
)


KT = ty.TypeVar("KT")
VT = ty.TypeVar("VT")


def configure_logging(verbose: bool) -> None:
    """Configure stream logging"""
    level = logging.DEBUG if verbose else logging.INFO
    _logger.setLevel(level)
    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.addFilter(lambda record: record.levelno < logging.WARNING)
    stdout_handler.setFormatter(logging.Formatter("%(module)s: %(message)s"))

    stderr_handler = logging.StreamHandler()
    stderr_handler.setLevel(logging.WARNING)
    stderr_handler.setFormatter(logging.Formatter("%(levelname)s: %(module)s: %(message)s"))

    _logger.addHandler(stdout_handler)
    _logger.addHandler(stderr_handler)


def add_config_file_argument(parser: argparse.ArgumentParser) -> None:
    """Add the config file argument to a argument parser"""
    parser.add_argument(
        "config_file",
        metavar="CONFIG_FILE",
        type=pathlib.Path,
        help="Configuration file for the scraper",
    )


def get_argument_parser() -> argparse.ArgumentParser:
    example_config_file_text = textwrap.indent(
        DEFAULT_CONFIG.model_dump_json(indent=2),
        prefix="    ",
    )

    parser = argparse.ArgumentParser(
        prog="ek-scraper",
        description=(
            f"Scraper for kleinanzeigen.de search results.\n\nExample configuration file:\n\n{example_config_file_text}"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument("--verbose", "-v", action="store_true", default=False, help="Enable verbose output")

    subparsers = parser.add_subparsers()
    run_parser = subparsers.add_parser("run", help="Run the scraper")

    data_store_group = run_parser.add_mutually_exclusive_group(required=True)
    data_store_group.add_argument(
        "--data-store",
        dest="data_store_file",
        type=pathlib.Path,
        default=pathlib.Path.home() / "ek-scraper-datastore.json",
        help="JSON file to store parsed ads [default: %(default)s]",
    )
    data_store_group.add_argument(
        "--temp-data-store",
        dest="data_store_file",
        action="store_const",
        const=TEMP_DATA_STORE_SENTINEL,
        help="Run the program on a temporary data store",
    )

    run_parser.add_argument(
        "--no-notifications",
        dest="send_notifications",
        action="store_false",
        default=True,
        help="Disable the sending of notifications for this run, useful to fill up the data store",
    )
    run_parser.add_argument(
        "--prune",
        dest="prune_data_store",
        action="store_true",
        default=False,
        help="Prune ads not seen anymore from the datastore",
    )
    add_config_file_argument(run_parser)
    run_parser.set_defaults(__func__=run)

    create_config_parser = subparsers.add_parser("create-config", help="Create a default config for the scraper")
    add_config_file_argument(create_config_parser)
    create_config_parser.set_defaults(__func__=create_config)

    prune_parser = subparsers.add_parser("prune", help="Prune all non-available results from the data store")
    add_config_file_argument(prune_parser)
    prune_parser.add_argument(
        "--data-store",
        dest="data_store_file",
        required=True,
        type=pathlib.Path,
        default=pathlib.Path.home() / "ek-scraper-datastore.json",
        help="JSON file to store parsed ads [default: %(default)s]",
    )
    prune_parser.set_defaults(__func__=prune)
    return parser


@contextlib.contextmanager
def get_data_store_file(data_store_file: pathlib.Path | object) -> ty.Generator[pathlib.Path, None, None]:
    """Get the data store file to use

    :param data_store_file: Path to the file to use or sentinel to use a temporary file
    :yield: Path of the file to use as a data store
    """
    if data_store_file is TEMP_DATA_STORE_SENTINEL:
        with tempfile.NamedTemporaryFile(mode="w+") as temp_file:
            yield pathlib.Path(temp_file.name)
        return

    if isinstance(data_store_file, pathlib.Path):
        yield data_store_file
        return

    raise ValueError(f"Invalid data store file definition {data_store_file}")


def get_first_key_and_value(data: collections.abc.Mapping[KT, VT], *keys: KT | None) -> tuple[KT, VT]:
    """Get the (key, value) tuple of the first key that matches. Ignore `None` keys.

    :param data: Mapping to get the data from
    :raises KeyError: Raised if none of the keys match
    :return: 2-tuple of (key, value) of the first matching key
    """
    for key in keys:
        if key is None:
            continue
        try:
            return key, data[key]
        except KeyError:
            pass
    raise KeyError(", ".join(repr(key) for key in keys))


def get_notification_names_and_configured_callbacks(
    notifications_config: NotificationsConfig,
) -> ty.Generator[tuple[str, ConfiguredSendNotifications], None, None]:
    """Generator that yields 2-tuples of (name, ConfiguredSendNotification)

    :param notifications_config: Configuration of all notifications
    :yield: 2-tuples containing the name of a callback and a partial which already has the config applied
    """
    for notification_type, notification_config in notifications_config:
        if notification_config is None:
            # No notification config is set for the notification type, continue
            continue
        try:
            alias = notifications_config.model_fields[notification_type].alias
            name, cb = get_first_key_and_value(NOTIFICATION_CALLBACKS, notification_type, alias)
        except KeyError:
            _logger.error("No notification callback registered for notification type '%s'", notification_type)
            continue

        yield name, functools.partial(cb, config=notification_config)


async def run(
    data_store_file: pathlib.Path | object,
    config_file: pathlib.Path,
    send_notifications: bool,
    prune_data_store: bool,
    **kwargs: ty.Any,
) -> None:
    """Implementation of the `run` command

    :param data_store_file: File to open the data store in
    :param config_file: Path of the configuration file
    :param send_notifications: Whether to send notifications after execution
    :param prune_data_store: Whether to prune the data store on close
    """
    config = Config.model_validate_json(config_file.read_text())

    with (
        get_data_store_file(data_store_file) as _data_store_file,
        DataStore(path=_data_store_file, prune_on_close=prune_data_store) as data_store,
    ):
        tasks: list[collections.abc.Awaitable[Result]] = list()
        for search in config.searches:
            tasks.append(get_filtered_search_result(search, config.filter, data_store=data_store))

        results: list[Result] = await asyncio.gather(*tasks)

    for result in results:
        _logger.info(
            "%d new results for query '%s', %d results already in data store, excluded %d results",
            len(result.ad_items),
            result.search_config.name,
            result.num_already_in_datastore,
            result.num_excluded,
        )

    if not send_notifications:
        _logger.info("Skip triggering notifications")
        return

    for notification_type, notification_callback in get_notification_names_and_configured_callbacks(
        config.notifications
    ):
        _logger.info("Call notification callback for '%s'", notification_type)
        await notification_callback(results)


def create_config(config_file: pathlib.Path, **kwargs: ty.Any) -> None:
    """Implementation of the `create-config` command

    :param config_file: Path of the configuration file
    """
    config_file.write_text(DEFAULT_CONFIG.model_dump_json(indent=2, by_alias=True, exclude_none=True))
    _logger.info("Created default config file at '%s'", config_file)


async def prune(data_store_file: pathlib.Path | object, config_file: pathlib.Path, **kwargs: ty.Any) -> None:
    """Implementation of the `prune` command

    :param data_store_file: File to open the data store in
    :param config_file: Path of the configuration file
    """
    config = Config.model_validate_json(config_file.read_text())

    tasks: list[collections.abc.Awaitable[ty.Any]] = []
    with (
        get_data_store_file(data_store_file) as _data_store_file,
        DataStore(path=_data_store_file, prune_on_close=True) as data_store,
    ):
        for search in config.searches:
            tasks.append(mark_ad_items_as_non_pruneable(search, data_store))
        await asyncio.gather(*tasks, return_exceptions=False)


async def async_main() -> ty.NoReturn:
    """Async main function."""
    parser = get_argument_parser()
    namespace = parser.parse_args()
    configure_logging(namespace.verbose)

    try:
        func = namespace.__func__
    except AttributeError:
        parser.error(parser.format_usage())

    try:
        ret = func(**vars(namespace))
        if inspect.isawaitable(ret):
            await ret
    except UnexpectedHTMLResponse as exc:
        parser.exit(
            status=1,
            message=(
                f"An unexpected response was received from kleinanzeigen.de. Maybe your IP address was blocked\n{exc}"
            ),
        )
    except Exception as exc:
        if namespace.verbose:
            _logger.exception("Error!")
        parser.exit(status=1, message=str(exc))

    parser.exit(status=0)


def main() -> None:
    asyncio.run(async_main())


if __name__ == "__main__":
    main()
