from __future__ import annotations

import logging
import pathlib
import typing as ty

import pydantic

__all__ = ["DataStore", "AdItem"]

_logger = logging.getLogger(__name__)


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
    pruneable: bool = pydantic.Field(default=True, exclude=True)


class _DataStoreData(pydantic.BaseModel):
    ad_items: dict[str, AdItem] = pydantic.Field(default_factory=dict)

    def __contains__(self, key: object) -> bool:
        return key in self.ad_items

    def add(self, ad_item: AdItem) -> bool:
        """Add an AdItem to the data store if it does not contain it yet

        :param ad_item: AdItem to add to the datastore
        :return: True if the item was added, False otherwise
        """
        if ad_item.id in self.ad_items:
            _logger.debug("Ad item '%s' with ID %s already in data store", ad_item.title, ad_item.id)
            self.ad_items[ad_item.id].pruneable = False
            return False

        ad_item.pruneable = False
        _logger.debug("Ad item '%s' with ID '%s' added to data store", ad_item.title, ad_item.id)
        self.ad_items[ad_item.id] = ad_item
        return True

    def prune(self) -> None:
        """Drop all AdItems marked as pruneable from the data store"""
        pruneable_ids: list[str] = []
        for ad_item_id, ad_item in self.ad_items.items():
            if ad_item.pruneable:
                pruneable_ids.append(ad_item_id)

        _logger.info("Pruning %d items from the data store", len(pruneable_ids))
        for pruneable_id in pruneable_ids:
            del self.ad_items[pruneable_id]

    def mark_as_non_pruneable(self, ad_item: AdItem) -> None:
        """Mark an AdItem as non-pruneable

        :param ad_item: AdItem to mark as non-pruneable
        """
        if ad_item_ := self.ad_items.get(ad_item.id):
            ad_item_.pruneable = False


class DataStore:
    """Data store backed by a JSON file"""

    def __init__(self, path: pathlib.Path, prune_on_close: bool) -> None:
        self._path = path
        self._data = _DataStoreData()
        self._prune_on_close = prune_on_close

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
        except FileNotFoundError:
            _logger.warning("Data store does not exist at '%s', will be created when closing", self._path)

    def close(self) -> None:
        if self._prune_on_close:
            self.prune()
        self._path.write_text(self._data.model_dump_json(by_alias=True, exclude_none=True))

    def prune(self) -> None:
        """Drop all AdItems marked as pruneable from the data store"""

        self._data.prune()

    def __contains__(self, ad_item: AdItem) -> bool:
        return ad_item in self._data

    def add(self, ad_item: AdItem) -> bool:
        """Add an AdItem to the data store if it does not contain it yet

        :param ad_item: AdItem to add to the datastore
        :return: True if the item was added, False otherwise
        """
        return self._data.add(ad_item)

    def mark_as_non_pruneable(self, ad_item: AdItem) -> None:
        """Mark an AdItem as non-pruneable

        :param ad_item: AdItem to mark as non-pruneable
        """
        self._data.mark_as_non_pruneable(ad_item)
