# Gold Answer: task_005

## Expected Core Answer

The likely root cause is that `ftp://example.com` uses a URL scheme without a mounted Requests adapter.
Requests sessions mount default adapters for `https://` and `http://`, not `ftp://`.

The relevant path is:

- High-level `requests.get(...)` uses a session request path.
- `Session.send` in `src/requests/sessions.py` calls `get_adapter(url)`.
- `Session.get_adapter` searches mounted adapter prefixes and raises `InvalidSchema` when no adapter
  matches the URL.
- `InvalidSchema` is defined in `src/requests/exceptions.py`.

The first files to inspect are `src/requests/sessions.py`, then `src/requests/adapters.py`, then
`src/requests/exceptions.py`.

## Required Files

- `src/requests/sessions.py`
- `src/requests/adapters.py`
- `src/requests/exceptions.py`

## Optional Supporting Files

- `tests/test_requests.py`
- `src/requests/api.py`

## Verified Evidence At Pinned SHA

- `src/requests/sessions.py` mounts `https://` and `http://` adapters in `Session.__init__`.
- `src/requests/sessions.py` defines `get_adapter` and raises `InvalidSchema` with the message
  `No connection adapters were found for ...` when no prefix matches.
- `src/requests/exceptions.py` defines `class InvalidSchema`.
- `tests/test_requests.py` has tests expecting `InvalidSchema` for malformed adapter inputs.

## Unacceptable Hallucinations

- Blaming DNS, TLS, proxy, or urllib3 retry behavior as the primary cause.
- Claiming Requests supports FTP by default.
- Claiming the exception comes from `adapters.py` for this specific no-adapter path.

## Expected Caveats

- A custom adapter mounted for `ftp://` could change the outcome.
- Some malformed URLs can also trigger `InvalidSchema`, but the provided FTP URL points to unsupported
  scheme routing.

## Scoring Notes

- Full correctness requires naming unsupported scheme/no mounted adapter and the `Session.get_adapter`
  error path.
- Strong debugging answers prioritize the exact first files to inspect.
