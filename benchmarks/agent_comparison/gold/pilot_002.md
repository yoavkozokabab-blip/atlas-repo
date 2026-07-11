# Gold: pilot_002 — Retry behavior (requests)

## Expected core answer

HTTP retry behavior for outgoing requests is configured in `src/requests/adapters.py`:

- `HTTPAdapter` sets `self.max_retries` using `urllib3.util.retry.Retry`
- Default: `Retry(0, read=False)` when not overridden
- Retry failures surface as `RetryError` / `MaxRetryError` handling

The retry **policy implementation** comes from **urllib3** (`urllib3.util.retry.Retry`), not a custom requests-only retry module.

## Required files

- `src/requests/adapters.py`

## Optional supporting files

- `src/requests/exceptions.py` (`RetryError`)
- urllib3 Retry (external dependency, mention by name)

## Unacceptable hallucinations

- Claiming retry logic is in `sessions.py` alone without adapters
- Inventing `retry.py` in requests
- Saying requests implements exponential backoff natively in a standalone file

## Expected caveats

- Actual retry execution is delegated to urllib3 connection pool
- `services/http_client.py` in atlas_reference is NOT part of this repo

## Scoring rubric (0–5 each)

| Dimension | 5 | 0 |
|---|---|---|
| Correctness | Identifies adapters.py + urllib3 Retry | Wrong file or no urllib3 |
| Completeness | Mentions HTTPAdapter / max_retries | Hand-wavy "requests retries" |
| File citation accuracy | adapters.py path correct | Wrong path |
| Evidence quality | Names Retry class or MaxRetryError | No code-level anchor |
| Hallucination avoidance | No invented retry module | Invents retry.py |
| Actionability | Points engineer to adapter config | Cannot locate code |
