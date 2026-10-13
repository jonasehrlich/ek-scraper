<!-- markdownlint-disable MD024 -->
# Changelog

## v0.3.0

### Added

* Add support for email notifications via SMTP with STARTTLS ([#281])
* Log a warning if a search result page seems to contain ads, but none could be parsed ([#308])

### Changed

* Add CI workflow running ruff, ty and the package build, and only publish to PyPI after it passed ([#308])
* Replace isort with ruff import sorting ([#308])

### Fixed

* Fix parsing of ads and pagination links after markup changes on kleinanzeigen.de ([#308])
* Fix type of the `smtp_port` email option to integer, ports given as strings are still accepted ([#308])
* Fix invalid JSON in the example configuration in the README ([#302])

## v0.2.4

### Changed

* Require Python 3.11 or newer, previously 3.9 (`c1045ae`)
* Switch from poetry to uv and hatchling for build and dependency management (`c1045ae`)
* Publish to PyPI using uv and trusted publishing (`1f50de2`, `a0c6b4a`)
* Recommend installing with `uv tool install` instead of pipx in the README (`5545f88`)

## v0.2.3

### Fixed

* Fix loading of configuration files with `exclude_patterns`, which failed with a validation error (`2bbbeb1`)

## v0.2.2

### Changed

* Raise specific error when we receive a non-`text/html` response. This can indicate an error or a block of the IP
  address

## v0.2.1

### Changed

* Remove unnecessary YAML front-matter from README file

## v0.2.0

> **This version introduces a breaking change to the data store format**

### Added

* Add support for [ntfy.sh](https://ntfy.sh) as a notification service ([#48])
* Add `--temp-data-store` CLI flag to run with a temporary, empty data-store

### Changed

* Use [pydantic](https://pydantic.dev) for data validation and serialization ([#49])
* Update runtime dependencies to latest versions
  * *lxml* from 4.9.2 to 4.9.4
  * *aiohttp* from 3.8.4 to 3.9.1

## v0.1.0

### Changed

* Switch to poetry for build and dependency management ([#8])

### Fixed

* Fix parsing of the ad location from HTML ([#9])
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

[#8]: https://github.com/jonasehrlich/ek-scraper/pull/8
[#9]: https://github.com/jonasehrlich/ek-scraper/pull/9
[#48]: https://github.com/jonasehrlich/ek-scraper/pull/48
[#49]: https://github.com/jonasehrlich/ek-scraper/pull/49
[#281]: https://github.com/jonasehrlich/ek-scraper/pull/281
[#302]: https://github.com/jonasehrlich/ek-scraper/pull/302
[#308]: https://github.com/jonasehrlich/ek-scraper/pull/308
