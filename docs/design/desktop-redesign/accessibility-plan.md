# Accessibility plan

## Contract

- Semantic banner, navigation, main, complementary inspector, dialogs, status, alerts, tables, lists, and headings.
- One `h1` in the active workspace; inactive views hidden from accessibility APIs.
- Skip link to the active workspace.
- Visible `:focus-visible`; logical order; focus return; no traps.
- Native buttons/links for every action. No click-only `div`/`span` controls.
- State uses text/icons in addition to color.
- `aria-live=polite` for scan and completion; errors alert only when action is required.
- Scan exposes a real progressbar. Inputs use `aria-invalid` and `aria-describedby`.
- Dialogs use `role=dialog`, `aria-modal=true`, names, focus containment, Escape where safe, and inert background.
- Graph has an accessible name/instructions and an equivalent searchable list in every mode. Selection exposes `aria-selected` and is announced.
- Text remains usable at 200% zoom and Windows text scaling. Reduced motion removes nonessential animation and smooth scroll.

## Verification

- Keyboard-only launch, local mode, scan, Ask, evidence, Impact, Graph list, Agents, Diagnostics, Settings.
- Duplicate-ID, accessible-name, landmark, label, and contrast audits.
- NVDA smoke test of repository selector, progress, confidence, graph alternative, and destructive confirmations.
- WCAG AA text and state contrast; essential control boundaries reach 3:1.
- Admin tabs implement the ARIA tabs pattern; route state uses `aria-current`.
