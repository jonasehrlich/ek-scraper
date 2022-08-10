from __future__ import annotations

import asyncio
import collections
import collections.abc
import dataclasses
import json
import logging
import pathlib
import re
import typing as ty
from urllib.parse import urljoin

import aiohttp
import bs4

_logger = logging.getLogger(__name__.split(".", 1)[0])

T = ty.TypeVar("T")


async def achain(*iterables: ty.AsyncIterable[T]) -> ty.AsyncIterator[T]:
    """Async chaining of iterables"""
    for iterable in iterables:
        async for item in iterable:
            yield item


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
    recursive: bool = True


@dataclasses.dataclass(frozen=True)
class FilterConfig:
    """Configuration of filters"""

    exclude_topads: bool = True
    exclude_patterns: list[str] = dataclasses.field(default_factory=list)


@dataclasses.dataclass
class Config:
    """Overall configuration object"""

    filter: FilterConfig = dataclasses.field(default_factory=FilterConfig)
    notifications: dict[str, dict[str, ty.Any]] = dataclasses.field(default_factory=dict)
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
    num_already_in_datastore: int = 0
    num_excluded: int = 0
    aditems: list[AdItem] = dataclasses.field(default_factory=list)


async def get_soup(session: aiohttp.ClientSession, url: str) -> bs4.BeautifulSoup:
    """Get the website and parse its markup using BeautifulSoup"""
    _logger.info("Getting soup for '%s'", url)
    # Tell the website we are a Chrome browser
    user_agent = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/104.0.0.0 Safari/537.36"
    async with session.get(url, headers={"User-Agent": user_agent}) as response:
        content = await response.text()
        return bs4.BeautifulSoup(content, features="lxml")


def get_all_page_urls(soup: bs4.BeautifulSoup, url: str) -> list[str]:
    """Get the URL of all anchor elements with class pagination-page

    :param soup: BeautifulSoup object to get the pagination URLS from
    :type soup: bs4.BeautifulSoup
    :param url: URL of the `soup` object to build absolute URLs
    :type url: str
    :return: List of URLs
    :rtype: list[str]
    """
    anchors = soup.select("a.pagination-page")
    return [urljoin(url, href) for link_element in anchors if isinstance(href := link_element.get("href"), str)]


async def resolve_all_pages(session: aiohttp.ClientSession, url: str, soup_map: dict[str, bs4.BeautifulSoup]) -> None:
    """Get URL of all anchor elements with class pagination-page"""
    _logger.info("Find pages linked on '%s'", url)
    soup = soup_map[url]
    if soup is None:
        soup = await get_soup(session, url)
        soup_map[url] = soup

    page_urls = get_all_page_urls(soup, url)

    if missing_pages := set(page_urls).difference(set(soup_map)):
        plural = "" if len(missing_pages) == 1 else "s"
        _logger.info("Found %d new page%s on '%s'", len(missing_pages), plural, url)

        async def add_to_soup_map(session: aiohttp.ClientSession, url: str):
            soup_map[url] = await get_soup(session, url)

        await asyncio.gather(*[add_to_soup_map(session, url_) for url_ in missing_pages])
        await resolve_all_pages(session, page_urls[-1], soup_map)


async def get_aditems_from_soup(soup: bs4.BeautifulSoup, url: str) -> ty.AsyncGenerator[AdItem, None]:
    """Get all ad items in a list of BeatifulSoup objects"""
    _logger.debug("Find all ad items in '%s'", url)
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
        soup_map = {search_config.url: (await get_soup(session, search_config.url))}
        if search_config.recursive:
            await resolve_all_pages(session, search_config.url, soup_map)

        async for aditem in achain(*[get_aditems_from_soup(soup, url) for url, soup in soup_map.items()]):
            if aditem.id in data_store:
                _logger.debug("Ad item '%s' with ID %s already in data store", aditem.title, aditem.id)
                result.num_already_in_datastore += 1
                continue

            exclude_aditem = False

            _logger.debug("Ad item '%s' with ID '%s' added to data store", aditem.title, aditem.id)
            data_store[aditem.id] = aditem

            if filter_config.exclude_topads and aditem.is_topad:
                exclude_aditem = True

            if not exclude_aditem:
                for pattern in exclude_patterns:
                    if pattern.search(aditem.title):
                        _logger.info(
                            "Title of ad '%s' '%s' matches exclude pattern '%s'",
                            aditem.id,
                            aditem.title,
                            pattern.pattern,
                        )
                        exclude_aditem = True
                        break

                    if pattern.search(aditem.description):
                        _logger.info(
                            "Description of ad '%s' '%s' matches exclude pattern '%s'",
                            aditem.id,
                            aditem.description,
                            pattern.pattern,
                        )
                        exclude_aditem = True
                        break

            if exclude_aditem:
                result.num_excluded += 1
                continue

            result.aditems.append(aditem)

        return result


def load_config(config_file: pathlib.Path) -> Config:
    """Load the configuration from the config path"""
    with open(config_file) as f:
        config_dict = json.load(f)

    filter_config = FilterConfig(**config_dict.get("filter", dict()))
    searches = [SearchConfig(**s) for s in config_dict.get("searches", list())]

    if not searches:
        _logger.warning("No searches configured in '%s'", config_file)

    notifications = config_dict.get("notifications", dict())
    if not notifications:
        _logger.warning("No notifications configured in '%s'", config_file)
    return Config(filter=filter_config, notifications=notifications, searches=searches)
