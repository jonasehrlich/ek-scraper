from __future__ import annotations

import asyncio
import collections.abc
import dataclasses
import json
import logging
import pathlib
import typing as ty
from urllib.parse import urljoin

import aiohttp
import bs4
import pydantic

from .config import FilterConfig, SearchConfig

_logger = logging.getLogger(__name__.split(".", 1)[0])

T = ty.TypeVar("T")


async def achain(*iterables: ty.AsyncIterable[T]) -> ty.AsyncIterator[T]:
    """Async chaining of iterables"""
    for iterable in iterables:
        async for item in iterable:
            yield item


class AdItem(pydantic.BaseModel):
    """Definition of an Ad item"""

    id: str
    url: str
    title: str
    description: str
    location: str
    price: str
    is_top_ad: bool
    image_url: str | None = None


class _DataStoreData(pydantic.BaseModel):
    ad_items: dict[str, AdItem] = pydantic.Field(default_factory=dict)

    def __contains__(self, key: object) -> bool:
        return key in self.ad_items

    def __setitem__(self, key: str, item: AdItem) -> None:
        self.ad_items[key] = item

    def __getitem__(self, key: str) -> AdItem:
        return self.ad_items[key]


class DataStore:
    """Dict-like object backed by a JSON file"""

    def __init__(self, path: pathlib.Path) -> None:
        self._path = path
        self._data = _DataStoreData()

    def __enter__(self) -> DataStore:
        self.open()
        return self

    def __exit__(self, *args: ty.Any) -> None:
        self.close()

    def open(self) -> None:
        try:
            if self._path.stat().st_size == 0:
                # The file is empty, nothing to decode
                return
            self._data = _DataStoreData.model_validate_json(self._path.read_text())
        except pydantic.ValidationError:
            _logger.error("Possibly invalid data store schema, please delete your data store and start from scratch")
            raise
        except json.JSONDecodeError:
            _logger.error("Error decoding non-empty file '%s'", self._path)
            raise
        except FileNotFoundError:
            _logger.warning("Data store does not exist at '%s', will be created when closing", self._path)

    def close(self) -> None:
        self._path.write_text(self._data.model_dump_json(by_alias=True, exclude_none=True))

    def __contains__(self, ad_item: AdItem) -> bool:
        return ad_item in self._data

    def add(self, ad_item: AdItem) -> bool:
        """Add an AdItem to the data store if it does not contain it yet

        :param ad_item: AdItem to add to the datastore
        :return: True if the item was added, False otherwise
        """
        if ad_item.id in self._data:
            _logger.debug("Ad item '%s' with ID %s already in data store", ad_item.title, ad_item.id)
            return False

        _logger.debug("Ad item '%s' with ID '%s' added to data store", ad_item.title, ad_item.id)
        self._data[ad_item.id] = ad_item
        return True


@dataclasses.dataclass
class Result:
    """Results of search config"""

    search_config: SearchConfig
    num_already_in_datastore: int = 0
    num_excluded: int = 0
    ad_items: list[AdItem] = dataclasses.field(default_factory=list)

    def get_url(self) -> str:
        """Get the URL for notifications"""
        return self.search_config.url

    def get_title(self) -> str:
        """Get title for notifications"""
        return self.search_config.name

    def get_message(self) -> str:
        """Get the message to use in notifications"""
        plural = "" if len(self.ad_items) == 1 else "s"
        return f"🤖 Found {len(self.ad_items)} new ad{plural}"


async def get_soup(session: aiohttp.ClientSession, url: str) -> bs4.BeautifulSoup:
    """Get the website and parse its markup using BeautifulSoup"""
    _logger.info("Getting soup for '%s'", url)
    # Tell the website we are a Chrome browser
    user_agent = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/104.0.0.0 Safari/537.36"
    async with session.get(url, headers={"User-Agent": user_agent}) as response:
        content = await response.text()
        return bs4.BeautifulSoup(content, features="lxml")


def get_all_pagination_urls(soup: bs4.BeautifulSoup, url: str) -> list[str]:
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


async def resolve_all_pages(
    session: aiohttp.ClientSession, url: str, soup_map: collections.abc.MutableMapping[str, bs4.BeautifulSoup]
) -> None:
    """Get URL of all anchor elements with class pagination-page"""
    _logger.info("Find pages linked on '%s'", url)
    soup = soup_map[url]

    pagination_urls = get_all_pagination_urls(soup, url)

    if missing_pages := set(pagination_urls).difference(set(soup_map)):
        plural = "" if len(missing_pages) == 1 else "s"
        _logger.info("Found %d new page%s on '%s'", len(missing_pages), plural, url)

        async def add_to_soup_map(session: aiohttp.ClientSession, url: str) -> None:
            soup_map[url] = await get_soup(session, url)

        await asyncio.gather(*[add_to_soup_map(session, url_) for url_ in missing_pages])
        await resolve_all_pages(session, pagination_urls[-1], soup_map)


async def get_ad_items_from_soup(soup: bs4.BeautifulSoup, url: str) -> ty.AsyncGenerator[AdItem, None]:
    """Get all ad items in a list of BeautifulSoup objects"""
    _logger.debug("Find all ad items in '%s'", url)
    for bs_ad_item in soup.find_all("article", class_="aditem"):
        try:
            ad_item = AdItem(
                id=bs_ad_item.get("data-adid"),
                url=urljoin(url, bs_ad_item.get("data-href")),
                title=bs_ad_item.select(".text-module-begin>a")[0].text.strip(),
                description=bs_ad_item.select(".aditem-main--middle--description")[0].text.strip(),
                location=bs_ad_item.select('i[class*="icon-pin"]')[0].parent.text.strip(),
                price=bs_ad_item.select('p[class*="price"]')[0].text.strip(),
                image_url=bs_ad_item.select(".imagebox")[0].get("data-imgsrc"),
                is_top_ad=bool(bs_ad_item.select(".icon-feature-topad")),
            )
        except IndexError as exc:
            raise RuntimeError(
                "Error parsing ads, this is probably caused by changes on kleinanzeigen.de\n\n"
                "Please run this command again with the --verbose option and open an issue with its "
                "output at https://github.com/jonasehrlich/ek-scraper/issues"
            ) from exc
        yield ad_item


async def get_new_ad_items(search_config: SearchConfig, filter_config: FilterConfig, data_store: DataStore) -> Result:
    """
    Return a result for a search configuration

    The result will only contain all new AdItems which are not yet in the data store and not excluded by the filters

    :param search_config: Search configuration to get the AdItems from
    :type search_config: SearchConfig
    :param filter_config: Filter configuration for the AdItems
    :type filter_config: FilterConfig
    :param data_store: Data store object to check if ad_item is new
    :type data_store: DataStore
    :return: Result for this search configuration
    :rtype: Result
    """
    result = Result(search_config)

    async with aiohttp.ClientSession() as session:
        soup_map = {search_config.url: (await get_soup(session, search_config.url))}
        if search_config.recursive:
            await resolve_all_pages(session, search_config.url, soup_map)

        async for ad_item in achain(*[get_ad_items_from_soup(soup, url) for url, soup in soup_map.items()]):
            # First: try to add the AdItem to the datastore, if it is already available continue
            if not data_store.add(ad_item):
                result.num_already_in_datastore += 1
                continue
            # Second: check if the AdItem should be excluded
            if ad_item_is_excluded(ad_item, filter_config):
                result.num_excluded += 1
                continue
            # AdItem is good, add to results
            result.ad_items.append(ad_item)

        return result


def ad_item_is_excluded(ad_item: AdItem, filter_config: FilterConfig) -> bool:
    """Return whether an AdItem should be excluded from the results, based on the filter configuration

    :param ad_item: AdItem to check
    :param filter_config: Filter configuration
    :return: Whether to exclude this item
    """
    if filter_config.exclude_topads and ad_item.is_top_ad:
        return True

    for pattern in filter_config.exclude_patterns:
        if pattern.search(ad_item.title):
            _logger.info(
                "Title of ad '%s' '%s' matches exclude pattern '%s'",
                ad_item.id,
                ad_item.title,
                pattern.pattern,
            )
            return True

        if pattern.search(ad_item.description):
            _logger.info(
                "Description of ad '%s' '%s' matches exclude pattern '%s'",
                ad_item.id,
                ad_item.description,
                pattern.pattern,
            )
            return True
    return False
