<!-- markdownlint-disable MD024 -->
# Changelog

## v0.2.1

### Changed

* Remove unnecessary YAML front-matter from README file

## v0.2.0

> **This version introduces a breaking change to the data store format**

### Added

* Add support for [ntfy.sh](https://ntfy.sh) as a notification service (`5707d5b`)
* Add `--temp-data-store` CLI flag to run with a temporary, empty data-store

### Changed

* Use [pydantic](https://pydantic.dev) for data validation and serialization (`8d28907`)
* Update runtime dependencies to latest versions
  * *lxml* from 4.9.2 to 4.9.4
  * *aiohttp* from 3.8.4 to 3.9.1

## v0.1.0

### Changed

* Switch to poetry for build and dependency management (`b469870`)

### Fixed

* Fix parsing of the ad location from HTML (`6139b27`)
* Fix error message if no command is provided (`f340a24`)

## v0.0.5

### Fixed

* Fix import in *\_\_main\_\_.py* (`8c5b291`)
* Fix price extraction from aditem HTML (`9afff4d`)

## v0.0.4

### Fixed

* Fix imports in other modules (`18c17d0`)

## v0.0.3

### Fixed

* Fix imports in cli module (`cd70dee`)

## v0.0.2

Initial PyPI release

### Added

* Initial package setup
* PyPI release workflow
