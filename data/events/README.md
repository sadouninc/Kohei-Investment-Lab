# Event Calendar Source Contract

`data/events/calendar.json` is the canonical repository hand-off for scheduled events consumed by the Morning Dataset.

The Events Provider does **not** invent or scrape events. Upstream deterministic collectors or a human-reviewed import must populate this file from reliable sources.

## Required shape

```json
{
  "as_of": "2026-08-08",
  "source": "official/manual-reviewed aggregation",
  "coverage": {
    "earnings": true,
    "economic": true,
    "policy": true,
    "market_calendar": true,
    "company": true
  },
  "events": {
    "earnings": [],
    "economic": [],
    "policy": [],
    "market_calendar": [],
    "company": []
  }
}
```

Every event item must contain at least:

- `title` or `name`
- `date`, `scheduled_at`, or `timestamp`

Preserve these fields when known:

- timezone / offset-aware timestamp
- security code / company
- country / region
- source URL or source identifier
- importance / category from the source

## Empty day

An empty calendar must not be treated as a verified "no events" day merely because all arrays are empty. Only set:

```json
"empty_confirmed": true
```

when all five coverage flags are `true` and the upstream source explicitly confirmed complete coverage for that `as_of` date.

## Quality status

- fresh + complete coverage → `OK`
- fresh but incomplete coverage / malformed item → `PARTIAL`
- old calendar → `STALE`
- no file, no usable facts, or unconfirmed empty file → `MISSING`

This keeps missing event risk visible to the AI instead of silently converting missing data into "nothing scheduled".
