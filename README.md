# EK scraper

Simple scraper for Ebay Kleinanzeigen searches with notifications for new ads.

## Installation

Clone this repository

``` bash
git clone git@github.com:jonasehrlich/ek-scraper.git
```

Change into the repository

``` bash
cd ek-scraper
```

Install the repository using

``` bash
pip3 install .
```

## Usage

> For the full usage check the `ek-scraper --help` command

Create a configuration file using

``` bash
ek-scraper create-config <path/to/config.json>
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

Modify the configuration to include your API tokens and optionally the list of devices to send the notifications to.
See [Notifications](#notifications) for details on configuring multiple notification services.

Modify the search configurations to your liking. It is recommended to only add the first page of your search results
as the `url`, because the `recursive` attribute will automatically resolve any pagination happening in the search
results.

Run the following command to initialize the data store without sending any notifications

``` bash
ek-scraper run --no-notifications path/to/config.json
```

## Filter

Filters can be configured in the `filter` section of the configuration file to exclude specific ads from your scrape
results on the client side. The following settings can be configured.

| Name | Description |
| ---- | ----------- |
| `exclude_topads` | Whether to exclude top ads from the results (optional, defaults to true) |
| `exclude_patterns` | Case-insensitive regular expression patterns used to exclude ads (optional) |

## Searches

Searches can be configured in the `searches` array of the configuration file. Each of the searches can be configured
with the following parameters.

| Name | Description |
| ---- | ----------- |
| `name` | Name of the search, use a descriptive one (required) |
| `url` | URL of the first page of your search (required) |
| `recursive` | Whether to follow all pages of the search result <br/>(optional, defaults to true) |

## Notifications

Notifications can be configured in the `notifications` section of the configuration file.

### Push notifications using Pushover

`ek-scraper` supports push notifications to your devices using [Pushover](https://pushover.net/).
For further information on the service check their terms and conditions.

To configure _Pushover_ for notifications from the scraper, first register at the service and create an application
(e.g. `ek-scraper`). To use the service in `ek-scraper`, add the `pushover` object to the `notifications` object in your
configuration file and fill the API tokens. Selection of the devices which will receive the notifications, is supported using the `device` array.

| Name | Description |
| ----- | ---------- |
| `token` | API token of the Pushover app (required) |
| `user` | API token of the Pushover user (required) |
| `device` | List of device names to send the notifications to <br/>(optional, defaults to all devices) |

## Running `ek-scraper` regularly

In order to run `ek-scraper` regularly on a Unix-like system, configure it as a cronjob.

To configure a cronjob, run

``` bash
crontab -e
```

Edit the crontab table to run the command you want to run. A handy tool to check schedule configurations for cronjobs is [crontab.guru](https://crontab.guru/).

For more information on configuring cronjobs use your favorite search engine.
