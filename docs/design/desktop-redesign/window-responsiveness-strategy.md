# Window responsiveness strategy

## Matrix

| Class | Viewport |
| --- | --- |
| Compact | 900 x 650 |
| Laptop | 1280 x 720 |
| Standard | 1440 x 900 |
| Large | 1600 x 1000 |
| Ultrawide | 1920 x 1080 or wider |

Verify Windows scaling at 125% and 150% on installed-app hardware.

## Rules

- Rail: 224 px expanded, 72 px compact, never wraps.
- Status bar: one row; secondary status moves into disclosure before wrapping.
- Long-form reports cap reading width; tables, graphs, and evidence use available width.
- Map: 260 px explorer, flexible graph/list, 320 px inspector. At compact sizes side panels become mutually exclusive drawers.
- Forms put actions beside inputs only when at least 760 px remains; otherwise actions move below.
- No page-level horizontal scroll. Wide tables scroll only inside a labelled region.
- Dense controls are at least 32 x 32 px; primary actions are at least 40 px high.

## Baseline defect

At 900 x 650 the current topbar wraps into multiple rows with all labels still visible. The rail removes this structural failure. At 320 CSS px/200% zoom and 600 x 400, auth and dialogs must keep every action reachable.
