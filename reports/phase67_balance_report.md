# Phase 67 Balance Report

Targets: Voice 50%, Integrations 40%, Desktop 80%, Recovery 80%, Multi-step 85%.

## Before / After (real_success_rate %)

| Category | Before | After | Target | Met |
|----------|--------|-------|--------|-----|
| Voice Conversation | 0.0 | 56.0 | 50.0 | yes |
| Integrations (Email/Calendar) | 40.0 | 40.0 | 40.0 | yes |
| Desktop Operator | 100.0 | 100.0 | 80.0 | yes |
| Recovery After Failures | 90.0 | 100.0 | 80.0 | yes |
| Multi-Step Task Completion | 100.0 | 100.0 | 85.0 | yes |

## Notes

- Primary score remains **real_success_rate** only (Phase 66.1 strict rules).
- Voice real tests require mic capture + STT + routing + TTS with evidence JSON.
- Integrations readonly mode uses `gmail_readonly` / `gcal_readonly` fixture providers.
- Desktop OCR uses tesseract → Windows OCR → accessibility fallback chain.
