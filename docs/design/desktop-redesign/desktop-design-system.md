# Desktop design system

## Character

Atlas is a premium technical instrument: graphite surfaces, mineral-teal active state, warm off-white text, restrained indigo secondary state, thin borders, low radius, and almost no glow.

## Tokens

| Role | Value |
| --- | --- |
| Canvas | `#090b0d` |
| Rail | `#0d1012` |
| Surface 1 | `#111518` |
| Surface 2 | `#151b1e` |
| Hairline | `#343e43` |
| Text | `#ece9e1` |
| Muted | `#9da5a3` |
| Mineral teal | `#58c3b0` |
| Teal ink | `#07120f` |
| Indigo | `#7f8cff` |
| Warning | `#d7a85d` |
| Failure | `#e06c75` |
| Success | `#6cc59a` |

Typography uses `Space Grotesk` for restrained display labels when locally available, `Geist`/Segoe UI Variable for interface copy, and `Geist Mono`/Cascadia Code/Consolas for paths and evidence. Remote font loading is forbidden. Spacing uses 4, 8, 12, 16, 24, 32, and 48 px. Radii use 3, 5, and 7 px; dialogs may use 10 px. Focus is a 2 px teal outline with 2 px offset.

## Primitives

- App shell: rail + status bar + workspace + optional inspector.
- Repository switcher: name, path disclosure, freshness, scan/switch actions.
- Nav item: icon, text, active rule, optional labelled status.
- Toolbar, tabs, button, input, select, dialog, notification.
- Split panel and inspector panel.
- Data/evidence/file/symbol row and sticky-header table.
- Status badge with icon and text; never color-only.
- Empty/error/loading/progress state with one recovery action.
- Graph controls, list equivalent, code/path reference, copy action.

## Forbidden

- Rounded-card grids as page structure.
- Serif editorial headlines in workspaces.
- Cyan/blue glow around routine controls.
- Marketing claims inside the workbench.
- Fake metrics, decorative graphs, icon-only critical actions, hover-only meaning, nested cards, continuous motion.
