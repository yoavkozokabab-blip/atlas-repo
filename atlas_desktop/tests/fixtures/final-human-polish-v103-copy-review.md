# Atlas final human-polish copy review

| Original | Replacement | Reason |
|----------|-------------|--------|
| Runtime timed out | Atlas runtime is unavailable (only when `/api/health` fails) | Optional timeouts must not look like a broken app |
| Repository grounded | Repository active / repo name | Internal QA wording |
| Interrogate the repository model | Ask a question about the repository. | AI-generated verbosity |
| Atlas identifies affected systems | Plan the change before editing code. | Marketing tone in product UI |
| Atlas correlates the observed failure | Trace a failure through the repository. | Repetitive “Atlas does X” pattern |
| Atlas traces direct and transitive dependencies | See what depends on a file before changing it. | Over-explained workflow subtitle |
| Configuration verified | Client verification not completed / Verified | Misleading success for unverified clients |
| Test all connections | Verify available clients | Only Cursor has a completed handshake |
| Update config | Review configuration | Config write is not proof of connection |
| 3 / 3 configured agents | Configured: 3 · Verified: 1 | Separate configured from verified |
| Memory offline (with active repo) | Memory current / No repository | Contradicted main screen state |
| Atlas version plus combined feedback link | Current Atlas version plus separate bug/feature links | Public footer should stay minimal |
| Report bug / Suggest feature (combined) | Report a bug · Suggest a feature | Clearer actions |
| Repository context network (Agents kicker) | Agents | Decorative uppercase label |
| Engineering investigation (Plan/Debug/Impact kicker) | Kept one per screen where needed | Reduced repeated eyebrow labels |
| Verified locally | Restored / Local | Duplicate trust signal when Fresh already shown |
| No files selected (Ask, empty) | Hidden until analysis | Empty permanent panel noise |
| Your first implementation plan banner | Hidden | Floating promo banner before output |
