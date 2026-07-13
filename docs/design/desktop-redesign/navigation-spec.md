# Navigation specification

## Global behavior

- The rail is stable before and after scanning. Repository-required items stay visible and disabled with an explanation.
- Active state uses a 2 px mineral-teal inset rule, tinted surface, icon, text, and `aria-current="page"`.
- `Ctrl+1..4` routes to Home, Ask, Impact, and Graph. `Ctrl+K` opens command/search. `Escape` closes the top safe overlay.
- Keyboard navigation focuses the destination heading; pointer navigation preserves pointer context.
- Browser Back/Forward follows the existing hash route.

## Repository switcher

- Persistent in the status bar.
- No repository: `Select repository`.
- Ready: name plus Current/Stale label and last indexed time.
- Scanning: phase, percentage, and cancel within disclosure.
- Missing/moved/denied: direct error plus choose-again action.

## Compatibility routes

| Label | Existing route |
| --- | --- |
| Home | `home` |
| Graph | `center` |
| Ask | `ask` |
| Impact | `impact` |
| Debug | `investigate` |
| Plan | `build` |
| Handoff | `export` |

Memory, Files, Agents, Diagnostics, and Settings are additive client destinations built from existing fields/APIs. No API path is renamed.
