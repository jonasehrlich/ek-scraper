# EK Crawler

Simple crawler for Ebay Kleinanzeigen searches.

## Usage

Create a configuration file, e.g:

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
      "recursive": false
    }
  ]
}

```

Run

``` bash
ek-crawler path/to/config.json
```
