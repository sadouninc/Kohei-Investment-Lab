# OpenAI API Integration

## Purpose

This spike validates the minimum secure path for calling the OpenAI Responses API from GitHub Actions.

```text
GitHub Actions
  -> OPENAI_API_KEY from Actions Secret
  -> scripts/openai_spike.py
  -> OpenAI Responses API
  -> generated JSON artifact
```

The API key is never committed to the repository. The workflow receives it only at runtime from the repository secret named `OPENAI_API_KEY`.

## Manual test

Open GitHub Actions and run **OpenAI API Spike** with `workflow_dispatch`.

Expected result:

```json
{
  "status": "OK",
  "message": "OpenAI API connected successfully."
}
```

The workflow uploads `data/generated/openai/api-test.json` as the short-lived `openai-api-test` artifact.

## Model selection

The workflow uses repository variable `OPENAI_MODEL` when present. If it is not configured, the spike defaults to `gpt-5`.

Keeping the model in a variable allows model changes without modifying source code.

## Security rules

- Never commit an API key.
- Never print `OPENAI_API_KEY` or HTTP authorization headers.
- Keep the test workflow manual until API connectivity, billing and cost behavior are confirmed.
- Generated test output contains only non-sensitive connectivity status.
- Future Morning AI integration must consume the prepared Morning Dataset; it must not move deterministic Fact/Feature calculations into the AI layer.

## Next step

After this spike succeeds, connect:

```text
Morning Dataset
  -> OpenAI API
  -> Morning Analysis JSON
  -> review / archive
```

The first production integration should remain human-reviewable and should not place orders automatically.
