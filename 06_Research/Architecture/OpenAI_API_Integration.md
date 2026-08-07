# OpenAI API Integration

## Purpose

Sado Investment Lab separates deterministic data preparation from AI reasoning.

```text
GitHub Actions / Python
  -> Market / Investor DNA / Morning Dataset
  -> Fact and Feature preparation

Morning Dataset
  -> OpenAI Responses API
  -> AI Morning Report
  -> Human review
```

The API key is never committed to the repository. GitHub Actions receives it only at runtime from the repository secret named `OPENAI_API_KEY`.

## Connectivity spike

The manual **OpenAI API Spike** workflow validates the minimum secure path:

```text
GitHub Actions
  -> OPENAI_API_KEY from Actions Secret
  -> scripts/openai_spike.py
  -> OpenAI Responses API
  -> generated JSON artifact
```

Expected result:

```json
{
  "status": "OK",
  "message": "OpenAI API connected successfully."
}
```

## Production Morning Analyst

The **AI Morning Analyst** workflow runs at 08:45 JST on weekdays and also supports `workflow_dispatch`.

```text
08:40 JST  Morning Dataset preparation / diagnostics
08:45 JST  AI Morning Analyst
              |
              +-> regenerate Market Phase
              +-> regenerate Investor DNA
              +-> generate Morning Dataset
              +-> call OpenAI Responses API
              +-> write 05_Daily_Reports/Morning/YYYY-MM-DD.md
              +-> write diagnostics JSON
              +-> commit both to main
              +-> normal Pages workflow publishes the archive
```

This separation keeps the AI layer downstream of deterministic Fact / Feature preparation.

## Output and persistence

Reports are committed to:

```text
05_Daily_Reports/Morning/YYYY-MM-DD.md
```

API diagnostics are committed to:

```text
data/generated/diagnostics/openai/YYYY-MM-DD.json
```

GitHub Pages publishes a human-readable archive at:

```text
/reports/morning/
```

The report persists even when the user does not open ChatGPT that day.

## Data quality policy

The AI is instructed to use only Morning Dataset facts. `null`, `MISSING`, `PARTIAL`, and `STALE` values must remain uncertainty rather than being filled with guesses.

Unsupported sections should explicitly say that the data is insufficient for a conclusion.

## Diagnostics

Each successful API execution records:

- dataset date and schema version
- dataset quality status
- SHA-256 fingerprint of the exact input dataset
- model
- OpenAI response ID
- execution time
- input / output / total tokens
- optional estimated cost
- report path

Estimated cost is not hard-coded because model pricing can change. It is calculated only when repository variables `OPENAI_INPUT_COST_PER_MILLION` and `OPENAI_OUTPUT_COST_PER_MILLION` are configured. Otherwise it remains `null` with `pricing_not_configured`.

## Model selection

Both the spike and production workflow use repository variable `OPENAI_MODEL` when present and otherwise default to `gpt-5`.

Keeping the model in a variable allows model changes without modifying source code.

## Security rules

- Never commit an API key.
- Never print `OPENAI_API_KEY` or HTTP authorization headers.
- Keep credentials in GitHub Actions Secrets.
- Do not put broker credentials, account identifiers, or unnecessary personal information into public datasets or reports.
- AI output must remain reviewable and must not place orders automatically.
- Deterministic calculations belong in Python; context-aware interpretation belongs in the AI layer.

## Future expansion

The same foundation can later support:

```text
Morning Dataset -> Morning AI
Market Shock Dataset -> Intraday AI
Closing Dataset -> Evening Reflection
Decision / Outcome history -> AI self-evaluation
```

Knowledge such as Framework or Investor DNA should not be automatically rewritten from a single AI response. AI-generated improvement ideas should remain proposals until reviewed.
