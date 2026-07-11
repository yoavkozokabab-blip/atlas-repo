# Gold Answer: task_002

## Expected Core Answer

Requests retry behavior for the default HTTP transport adapter is configured in `src/requests/adapters.py`.
`DEFAULT_RETRIES` is `0`, and `HTTPAdapter.__init__` accepts `max_retries`. When `max_retries` is the
default, the adapter creates a retry object with no retries; otherwise it converts the supplied value
through urllib3 retry handling.

A `Session` reaches that adapter through `src/requests/sessions.py`. `Session.__init__` mounts default
`HTTPAdapter()` instances for `https://` and `http://`. During request sending, `Session.send` selects
an adapter with `get_adapter(url)` and delegates the actual network send to the adapter.

## Required Files

- `src/requests/adapters.py`
- `src/requests/sessions.py`

## Optional Supporting Files

- `src/requests/api.py`
- `src/requests/models.py`

## Verified Evidence At Pinned SHA

- `src/requests/adapters.py` contains `DEFAULT_RETRIES`, `class HTTPAdapter`, `HTTPAdapter.__init__`,
  `init_poolmanager`, and `send`.
- `src/requests/sessions.py` contains `Session.__init__`, default `self.mount("https://", HTTPAdapter())`
  and `self.mount("http://", HTTPAdapter())`, `Session.send`, and `get_adapter`.

## Unacceptable Hallucinations

- Saying the default Requests retry count is 3 or 5.
- Claiming retry policy is primarily configured in `sessions.py`.
- Claiming `requests.get` directly instantiates urllib3 pools without going through `Session` and adapter selection.

## Expected Caveats

- urllib3 provides the lower-level retry object and pool behavior, but this task asks where Requests wires
  retry behavior for the default adapter.
- User-supplied adapters can alter this path.

## Scoring Notes

- Full correctness requires both adapter retry setup and session-to-adapter routing.
- Citation accuracy should penalize answers that cite only urllib3 or only the high-level API wrapper.
