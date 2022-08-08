# EK Crawler

Simple crawler for Ebay Kleinanzeigen searches.

## Installation

Clone this repository

``` bash
git clone git@github.com:jonasehrlich/ek-crawler.git
```

Change into the repository

``` bash
cd ek-crawler
```

Install the repository using

``` bash
pip3 install .
```

## Usage

> For the full usage check the `ek-crawler --help` command

Create a configuration file using

``` bash
ek-crawler create-config <path/to/config.json>
```

The example configuration file will look like this:

```json

{
  "filter": {
    "exclude_topads": true,
    "exclude_patterns": []
  },
  "notifications": {
    "pushover": {
        "token": "<your-app-api-token>",
        "user": "<your-user-api-token>",
        "device": []
    }
  },
  "searches": [
    {
      "name": "Wohnungen in Hamburg Altona",
      "url": "https://www.ebay-kleinanzeigen.de/s-wohnung-mieten/altona/c203l9497",
      "recursive": true
    }
  ]
}

```

Modify the search configurations to your liking. It is recommended to only add the first page of your search results,
as the `recursive` attribute will automatically resolve any pagination happening in the search results.

Run the following command to initialize the data store without sending any notifications

``` bash
ek-crawler run --no-notifications path/to/config.json
```

### Configure notifications using Pushover

`ek-crawler` supports push notifications to your mobile devices using [Pushover](https://pushover.net/).
For further information on the service check their terms and conditions.

To configure _Pushover_ for notifications from the crawler, first register at the service and create an application
(e.g. `ek-crawler`). To use the service in `ek-crawler`, add the `pushover` object to the `notifications` object in your
configuration file and fill the API tokens. Additional filtering by device is supported using the `device` field.
