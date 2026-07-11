# Gold Answer: task_003

## Expected Core Answer

FastAPI builds request handling around `APIRoute` in `fastapi/routing.py`. Route construction creates
dependency models and stores route configuration. `APIRoute.get_route_handler` returns the request
handler produced by `get_request_handler`.

For an HTTP request, the handler in `fastapi/routing.py` parses the body when needed, calls
`solve_dependencies`, checks validation errors, then calls `run_endpoint_function` for the endpoint.
The response is converted through `serialize_response` unless the endpoint already returned a response
object.

Dependency and parameter resolution live in `fastapi/dependencies/utils.py`. `solve_dependencies`
recursively resolves dependencies, applies overrides through `dependency_overrides_provider`, converts
path/query/header/cookie parameters with `request_params_to_args`, and converts body fields with
`request_body_to_args`.

## Required Files

- `fastapi/routing.py`
- `fastapi/dependencies/utils.py`

## Optional Supporting Files

- `fastapi/dependencies/models.py`
- `fastapi/applications.py`
- `fastapi/params.py`

## Verified Evidence At Pinned SHA

- `fastapi/routing.py` contains `class APIRoute`, `APIRoute.get_route_handler`, `get_request_handler`,
  `solve_dependencies` calls, `run_endpoint_function`, and `serialize_response`.
- `fastapi/dependencies/utils.py` contains `solve_dependencies`, `request_params_to_args`, and body
  argument conversion helpers.

## Unacceptable Hallucinations

- Claiming Starlette alone performs FastAPI dependency solving.
- Omitting `fastapi/dependencies/utils.py`.
- Claiming endpoint execution happens before dependency solving.
- Treating WebSocket route handling as the primary HTTP request lifecycle.

## Expected Caveats

- Starlette provides the lower-level ASGI routing foundation, but FastAPI layers validation and
  dependency solving on top.
- WebSocket routes have a related but distinct path in `fastapi/routing.py`.

## Scoring Notes

- Full completeness requires route creation, handler construction, body/parameter handling, dependency
  solving, endpoint call, and response serialization.
- Strong answers cite functions, not just broad modules.
