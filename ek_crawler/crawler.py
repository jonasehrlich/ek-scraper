from __future__ import annotations

import argparse
import asyncio
import collections
import collections.abc
import dataclasses
import json
import logging
import pathlib
import re
import sys
import textwrap
import typing as ty
from urllib.parse import urljoin

import aiohttp
import bs4

_logger = logging.getLogger()


class DataclassesJSONEncoder(json.JSONEncoder):
    """JSON encoder with support for dataclasses"""

    def default(self, obj):
        if dataclasses.is_dataclass(obj):
            return dataclasses.asdict(obj)
        # Let the base class default method raise the TypeError
        return json.JSONEncoder.default(self, obj)


@dataclasses.dataclass(frozen=True)
class AdItem:
    """Definition of an Ad item"""

    id: str
    url: str
    title: str
    description: str
    added: ty.Optional[str]
    location: str
    price: str
    image_url: str
    is_topad: bool


@dataclasses.dataclass(frozen=True)
class SearchConfig:
    """Configuration of a search"""

    name: str
    url: str
    recursive: bool = False


@dataclasses.dataclass(frozen=True)
class FilterConfig:
    """Configuration of filters"""

    exclude_topads: bool = True
    exclude_patterns: ty.List[str] = dataclasses.field(default_factory=list)


@dataclasses.dataclass
class Config:
    """Overall configuration object"""

    filter: FilterConfig = dataclasses.field(default=FilterConfig())
    searches: list[SearchConfig] = dataclasses.field(default_factory=list)


class DataStore(collections.UserDict[str, AdItem]):
    """Dict-like object backed by a JSON file"""

    def __init__(self, path: pathlib.Path) -> None:
        self.path = path
        super().__init__()

    def __enter__(self) -> DataStore:
        self.open()
        return self

    def __exit__(self, *args):
        self.close()

    def open(self):
        try:
            with open(self.path) as f:
                self.data = {key: AdItem(**value) for key, value in json.load(f).items()}
        except FileNotFoundError:
            _logger.warning("Data store does not exist at '%s', will be created when closing", self.path)

    def close(self):
        with open(self.path, "w") as f:
            json.dump(self.data, f, cls=DataclassesJSONEncoder, indent=2)


@dataclasses.dataclass
class Result:
    """Results of search config"""

    search_config: SearchConfig
    num_excluded: int = 0
    aditems: ty.List[AdItem] = dataclasses.field(default_factory=list)


async def get_soup(session: aiohttp.ClientSession, url: str) -> bs4.BeautifulSoup:
    """Get the website and parse it using BeautifulSoup"""
    # Tell the website we are a Chrome browser
    user_agent = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/104.0.0.0 Safari/537.36"
    async with session.get(url, headers={"User-Agent": user_agent}) as response:
        content = await response.text()
        return bs4.BeautifulSoup(content, features="lxml")


def get_all_pagingation_urls(soup: bs4.BeautifulSoup, url: str) -> ty.List[str]:
    """Get URL of all anchor elements with class pagination-page"""
    _logger.info("Find pages linked in '%s'", url)
    anchors = soup.select("a.pagination-page")
    return [urljoin(url, href) for link_element in anchors if isinstance(href := link_element.get("href"), str)]


async def get_aditems_from_soups(soups: ty.List[bs4.BeautifulSoup], url: str) -> ty.AsyncGenerator[AdItem, None]:
    """Get all ad items in a list of BeatifulSoup objects"""
    _logger.debug("Find all ad items in '%s'", url)
    for soup in soups:
        for aditem in soup.find_all("article", class_="aditem"):
            calendar_icons = aditem.select(".icon-calendar-open")
            if calendar_icons:
                added = ty.cast(str, calendar_icons[0].parent.text.strip())
            else:
                added = None
            aditem = AdItem(
                id=aditem.get("data-adid"),
                url=urljoin(url, aditem.get("data-href")),
                title=aditem.select(".text-module-begin>a")[0].text.strip(),
                description=aditem.select(".aditem-main--middle--description")[0].text.strip(),
                location=aditem.select(".icon-pin")[0].parent.text.strip(),
                price=aditem.select(".aditem-main--middle--price")[0].text.strip(),
                added=added,
                image_url=aditem.select(".imagebox")[0].get("data-imgsrc"),
                is_topad=bool(aditem.select(".icon-feature-topad")),
            )
            yield aditem


async def get_new_aditems(search_config: SearchConfig, filter_config: FilterConfig, data_store: DataStore) -> Result:
    """
    Return a result for a search configuration

    The result will only contain all new AdItems which are not yet in the data store and not excluded by the filters

    :param search_config: Search configuration to get the AdItems from
    :type search_config: SearchConfig
    :param filter_config: Filter configuration for the AdItems
    :type filter_config: FilterConfig
    :param data_store: Data store object to check if aditem is new
    :type data_store: DataStore
    :return: Result for this search configuration
    :rtype: Result
    """
    result = Result(search_config)
    exclude_patterns = [re.compile(pattern, re.IGNORECASE) for pattern in filter_config.exclude_patterns]
    async with aiohttp.ClientSession() as session:

        soups = [await get_soup(session, search_config.url)]
        # TODO: recursively get additional soups from pagination

        async for aditem in get_aditems_from_soups(soups, search_config.url):
            if aditem.id in data_store:
                _logger.info("Ad item '%s' with ID %s already in data store", aditem.title, aditem.id)
                continue

            exclude_aditem = False

            _logger.debug("Ad item '%s' with ID '%s' added to data store", aditem.title, aditem.id)
            data_store[aditem.id] = aditem

            if filter_config.exclude_topads and aditem.is_topad:
                exclude_aditem = True

            if not exclude_aditem:
                for pattern in exclude_patterns:
                    if pattern.match(aditem.title):
                        _logger.debug(
                            "Title of ad '%s' '%s' matches exclude pattern '%s'",
                            aditem.id,
                            aditem.title,
                            pattern.pattern,
                        )
                        exclude_aditem = True
                        break

                    if pattern.match(aditem.description):
                        _logger.debug(
                            "Description of ad '%s' '%s' matches exclude pattern '%s'",
                            aditem.id,
                            aditem.description,
                            pattern.pattern,
                        )
                        exclude_aditem = True
                        break

            if exclude_aditem:
                continue
            result.num_excluded += 1
            result.aditems.append(aditem)

        return result


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


def load_config(config_file: pathlib.Path) -> Config:
    """Load the configuration from the config path"""
    with open(config_file) as f:
        config_dict = json.load(f)

    filter_config = FilterConfig(config_dict.get("filter", dict()))
    searches = config_dict.get("searches", list())

    if not searches:
        _logger.warning("No searches configured in '%s'", config_file)

    return Config(filter=filter_config, searches=searches)


def get_argument_parser() -> argparse.ArgumentParser:

    example_config_file_text = textwrap.indent(
        json.dumps(
            dataclasses.asdict(
                Config(
                    searches=[
                        SearchConfig(
                            name="Wohnungen in Hamburg Altona",
                            url="https://www.ebay-kleinanzeigen.de/s-wohnung-mieten/altona/c203l9497",
                        )
                    ]
                )
            ),
            indent=2,
        ),
        prefix="    ",
    )
    parser = argparse.ArgumentParser(
        prog="ek-crawler",
        description=(
            f"Crawler for Ebay Kleinanzeigen search results.\n\n"
            f"Example configuration file:\n\n{example_config_file_text}"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument("--verbose", "-v", action="store_true", default=False, help="Enable verbose output")
    parser.add_argument(
        "--data-store",
        type=pathlib.Path,
        default=pathlib.Path.home() / "ek-crawler-datastore.json",
        help="Data store where all already seen ads are stored [default: %(default)s]",
    )
    parser.add_argument(
        "config_file",
        metavar="CONFIG_FILE",
        type=pathlib.Path,
        help="Configuration file with the search configurations",
    )
    return parser


async def amain():
    parser = get_argument_parser()
    namespace = parser.parse_args()
    configure_logging(namespace.verbose)
    config = load_config(namespace.config_file)

    with DataStore(namespace.data_store) as data_store:
        tasks = list()
        for search in config.searches:
            tasks.append(get_new_aditems(search, config.filter, data_store=data_store))

        results: ty.List[Result] = await asyncio.gather(*tasks)

    for result in results:
        _logger.info("Results for query '%s', excluded %d results", result.search_config.name, result.num_excluded)
        for aditem in result.aditems:
        _logger.info(
            "%d new results for query '%s', %d results already in data store, excluded %d results",
            len(result.aditems),
            result.search_config.name,
            result.num_already_in_datastore,
            result.num_excluded,
        )


def main():
    asyncio.run(async_main())


if __name__ == "__main__":
    main()
