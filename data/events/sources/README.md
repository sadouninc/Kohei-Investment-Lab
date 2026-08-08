# Event Collector Inputs

These files are deterministic, reviewable inputs for `scripts/event_calendar_collector.py`.

Supported filenames/categories:

- `earnings.json`
- `economic.json`
- `policy.json`
- `market_calendar.json`
- `company.json`

Each file uses:

```json
{
  "coverage_confirmed": false,
  "events": [
    {
      "title": "Example event",
      "scheduled_at": "2026-08-08T15:00:00+09:00",
      "timezone": "Asia/Tokyo",
      "source_url": "official source URL"
    }
  ]
}
```

`coverage_confirmed: true` is a strong assertion: it means the upstream import/collector checked the category sufficiently for the target date. Do not set it merely because the file was generated successfully.

The aggregator never converts a missing source into confirmed empty coverage. If all five categories explicitly confirm coverage and contain no events, only then may the canonical calendar contain `empty_confirmed: true`.

## Source policy

Prefer official exchange/regulator/central-bank/government calendars and official company IR sources. Structured public data or human-reviewed imports may be used when stable official automation is unavailable. Preserve provenance (`source_url`, source identifier, timezone, security/company metadata) rather than copying article prose.

This directory is an ingestion boundary, not a news archive. Do not store secrets or brokerage credentials here.
