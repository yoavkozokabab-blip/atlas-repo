# Gold Answer: task_006

## Expected Core Answer

At the pinned Home Assistant Core commit, there is no built-in integration/domain named
`atlas_repository_context`. The required evidence is an absence check against the integration component
tree, not a guess from package names.

Acceptable evidence includes:

- `git ls-tree -d HEAD homeassistant/components/atlas_repository_context` returns no tree entry.
- A tree-name search under `homeassistant/components` for `atlas_repository_context` or an exact
  `atlas` component returns no matches.
- A positive-control path such as `homeassistant/components/websocket_api` exists, showing the tree
  check is pointed at the expected component root.

## Required Files Or Absence Checks

- Absence of `homeassistant/components/atlas_repository_context`
- Absence of a matching manifest path such as
  `homeassistant/components/atlas_repository_context/manifest.json`

## Optional Supporting Evidence

- `git ls-tree -d HEAD homeassistant/components/websocket_api` as a positive control.
- `git ls-tree -r --name-only HEAD homeassistant/components | rg -i "atlas_repository_context|(^|/)atlas($|/)"`

## Verified Evidence At Pinned SHA

- `git -C %TEMP%\\atlas_agent_bench_homeassistant_2989e6 rev-parse HEAD` returned
  `2989e6bcdf639489d2073276603a3c38d49eee21`.
- `git -C %TEMP%\\atlas_agent_bench_homeassistant_2989e6 ls-tree -d HEAD homeassistant/components/atlas_repository_context`
  returned no output.
- `git -C %TEMP%\\atlas_agent_bench_homeassistant_2989e6 ls-tree -d HEAD homeassistant/components/websocket_api`
  returned an existing tree entry.

## Unacceptable Hallucinations

- Inventing an Atlas integration, manifest, config flow, or service.
- Answering "probably not" without repository evidence.
- Treating unrelated occurrences of the word "atlas" outside `homeassistant/components` as an integration.

## Expected Caveats

- This proves absence at the pinned commit only.
- A custom user integration outside Home Assistant Core would not be represented in this repo.

## Scoring Notes

- Full credit requires a clear negative answer and concrete absence evidence.
- Penalize any answer that fabricates files to fill the negative control.
