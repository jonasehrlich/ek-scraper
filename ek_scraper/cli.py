import argparse
import asyncio
import dataclasses
import inspect
import json
import logging
import pathlib
import sys
import textwrap

from ek_scraper import notifications
from ek_scraper.__version__ import __version__
from ek_scraper.notifications import pushover
from ek_scraper.scraper import (
    Config,
    DataclassesJSONEncoder,
    DataStore,
    Result,
    SearchConfig,
    get_new_aditems,
    load_config,
)

_logger = logging.getLogger(__name__.split(".", 1)[0])


DUMMY_SEARCH_CONFIG = SearchConfig(
    name="Wohnungen in Hamburg Altona",
    url="https://www.ebay-kleinanzeigen.de/s-wohnung-mieten/altona/c203l9497",
)


def configure_logging(verbose: bool) -> None:
    """Configure stream logging"""
    level = logging.DEBUG if verbose else logging.INFO
    _logger.setLevel(level)
    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.addFilter(lambda record: record.levelno < logging.WARNING)
    stdout_handler.setFormatter(logging.Formatter("%(message)s"))

    stderr_handler = logging.StreamHandler()
    stderr_handler.setLevel(logging.WARNING)
    stderr_handler.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))

    _logger.addHandler(stdout_handler)
    _logger.addHandler(stderr_handler)


def add_config_file_argument(parser: argparse.ArgumentParser):
    """Add the config file argument to a argument parser"""

    parser.add_argument(
        "config_file",
        metavar="CONFIG_FILE",
        type=pathlib.Path,
        help="Configuration file for the scraper",
    )


def get_argument_parser() -> argparse.ArgumentParser:

    example_config_file_text = textwrap.indent(
        json.dumps(
            dataclasses.asdict(Config(searches=[DUMMY_SEARCH_CONFIG])),
            indent=2,
        ),
        prefix="    ",
    )
    parser = argparse.ArgumentParser(
        prog="ek-scraper",
        description=(
            f"Scraper for Ebay Kleinanzeigen search results.\n\n"
            f"Example configuration file:\n\n{example_config_file_text}"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__.__version__}")
    parser.add_argument("--verbose", "-v", action="store_true", default=False, help="Enable verbose output")

    subparsers = parser.add_subparsers()
    run_parser = subparsers.add_parser("run", help="Run the scraper")
    run_parser.add_argument(
        "--data-store",
        dest="data_store_file",
        type=pathlib.Path,
        default=pathlib.Path.home() / "ek-scraper-datastore.json",
        help="Data store where all already seen ads are stored [default: %(default)s]",
    )
    run_parser.add_argument(
        "--no-notifications",
        dest="send_notifications",
        action="store_false",
        default=True,
        help="Disable the sending of notifications for this run, useful to fill up the data store",
    )
    add_config_file_argument(run_parser)
    run_parser.set_defaults(__func__=run)

    create_config_parser = subparsers.add_parser("create-config", help="Create a default config for the scraper")
    add_config_file_argument(create_config_parser)
    create_config_parser.set_defaults(__func__=create_config)

    return parser


NOTIFICATION_CALLBACKS: dict[str, notifications.SendNotification] = {"pushover": pushover.send_notifications}


async def run(data_store_file: pathlib.Path, config_file: pathlib.Path, send_notifications: bool, **kwargs):

    config = load_config(config_file)
    with DataStore(data_store_file) as data_store:
        tasks = list()
        for search in config.searches:
            tasks.append(get_new_aditems(search, config.filter, data_store=data_store))

        results: list[Result] = await asyncio.gather(*tasks)

    for result in results:
        _logger.info(
            "%d new results for query '%s', %d results already in data store, excluded %d results",
            len(result.aditems),
            result.search_config.name,
            result.num_already_in_datastore,
            result.num_excluded,
        )

    if not send_notifications:
        _logger.info("Skip sending of notifications")
        return

    for notification_type, notification_settings in config.notifications.items():
        try:
            notification_callback = NOTIFICATION_CALLBACKS[notification_type]
        except KeyError:
            _logger.error("No notification callback registered for key '%s'", notification_type)
            continue
        _logger.info("Call notification callback for '%s'", notification_type)
        await notification_callback(results, notification_settings)


def create_config(config_file: pathlib.Path, **kwargs):
    with open(config_file, "w") as f:

        config = Config(
            notifications={"pushover": pushover.PushoverConfig.to_default_dict()}, searches=[DUMMY_SEARCH_CONFIG]
        )
        json.dump(config, f, cls=DataclassesJSONEncoder, indent=2)
    _logger.info("Created default config file at '%s'", config_file)


async def async_main():
    """Async main function."""
    parser = get_argument_parser()
    namespace = parser.parse_args()
    configure_logging(namespace.verbose)
    func = namespace.__func__

    try:
        ret = func(**vars(namespace))
        if inspect.isawaitable(ret):
            await ret
    except Exception as exc:
        if namespace.verbose:
            _logger.exception("Error!")

        parser.error(str(exc))


def main():
    asyncio.run(async_main())


if __name__ == "__main__":
    main()
