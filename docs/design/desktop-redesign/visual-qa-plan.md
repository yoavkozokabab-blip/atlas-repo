# Visual QA plan

## Required captures

Capture source and installed modes at 900 x 650, 1280 x 720, 1440 x 900, and 1920 x 1080:

- splash, startup failure, unsigned notice
- sign in, registration, local mode
- Home empty, ready, stale, productive
- repository selection, validation error, scan progress, cancellation, success, failure
- Memory, Files, Ask empty/loading/result/low confidence/error
- Impact, Debug, Plan empty/result/error
- Graph default/selected/list fallback/large repository
- Agents disconnected/configured/test failure
- Diagnostics healthy/degraded and Settings

## Checklist

- No clipped navigation, status, path, table, graph control, or primary action.
- No page-level horizontal overflow.
- Typography roles match the design system; paths and evidence are monospace.
- Focus, hover, active, selected, warning, failure, disabled, and destructive states are distinct.
- Skeletons match final geometry.
- Long Windows paths and large counts do not change control height.
- No fake data or decorative technical metrics.
- Map is legible without glow and always has a list equivalent.

Source-code completion alone is not a visual pass.
