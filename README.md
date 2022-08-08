# EK Crawler

Simple crawler for Ebay Kleinanzeigen searches.

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
  "searches": [
    {
      "name": "Wohnungen in Hamburg Altona",
      "url": "https://www.ebay-kleinanzeigen.de/s-wohnung-mieten/altona/c203l9497",
      "recursive": true
    }
  ]
}

```

Modify the search configurations to your liking.

Run

``` bash
ek-crawler run path/to/config.json
```

to initialize the data store.
