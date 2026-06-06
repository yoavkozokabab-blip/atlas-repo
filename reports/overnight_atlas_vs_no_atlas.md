# Overnight Atlas vs No Atlas

Conservative estimates only. No-Atlas context assumes focused manual context, not whole-repository paste. Speedup estimates are post-scan and include human review floors: Atlas impact is floored at 60s, Atlas investigation at 90s, and speedups are capped at 20x. First-run Atlas still pays scan time.

| Repo | No-Atlas context | Atlas compact context | Context reduction | Manual impact sec est | Atlas impact effective sec | Impact speedup | Manual investigation sec est | Atlas investigation effective sec | Investigation speedup |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| FastAPI | 47,816 | 325 | 99.32% | 300.00 | 60.00 | 5.00x | 420.00 | 90.00 | 4.67x |
| Django | 50,000 | 385 | 99.23% | 825.58 | 60.00 | 13.76x | 1024.00 | 90.00 | 11.38x |
| Pydantic | 50,000 | 400 | 99.20% | 300.00 | 60.00 | 5.00x | 420.00 | 90.00 | 4.67x |
| LangChain | 50,000 | 407 | 99.19% | 644.57 | 60.00 | 10.74x | 784.60 | 90.00 | 8.72x |
| React | 50,000 | 480 | 99.04% | 1018.00 | 60.00 | 16.97x | 1254.94 | 90.00 | 13.94x |
| Qdrant | 50,000 | 489 | 99.02% | 300.00 | 60.00 | 5.00x | 420.00 | 90.00 | 4.67x |
| OpenBB | 50,000 | 520 | 98.96% | 433.08 | 60.00 | 7.22x | 528.14 | 90.00 | 5.87x |
| Next.js | 50,000 | 588 | 98.82% | 3052.61 | 60.00 | 20.00x | 3600.00 | 90.00 | 20.00x |
| NestJS | 42,274 | 522 | 98.77% | 523.49 | 60.00 | 8.72x | 641.30 | 90.00 | 7.13x |
| Home Assistant | 50,000 | 634 | 98.73% | 3600.00 | 60.00 | 20.00x | 3600.00 | 90.00 | 20.00x |
| VS Code | 50,000 | 674 | 98.65% | 3280.53 | 60.00 | 20.00x | 3600.00 | 90.00 | 20.00x |
| Rich | 21,089 | 359 | 98.30% | 300.00 | 60.00 | 5.00x | 420.00 | 90.00 | 4.67x |
| Typer | 12,681 | 355 | 97.20% | 300.00 | 60.00 | 5.00x | 420.00 | 90.00 | 4.67x |
| SQLModel | 8,281 | 332 | 95.99% | 300.00 | 60.00 | 5.00x | 420.00 | 90.00 | 4.67x |
| QuixBugs | 8,000 | 400 | 95.00% | 300.00 | 60.00 | 5.00x | 420.00 | 90.00 | 4.67x |
| Requests | 8,000 | 434 | 94.58% | 300.00 | 60.00 | 5.00x | 420.00 | 90.00 | 4.67x |
| Flask | 8,000 | 449 | 94.39% | 300.00 | 60.00 | 5.00x | 420.00 | 90.00 | 4.67x |

## Aggregate

- measured repositories: 17
- average conservative context reduction: 97.91%
- average conservative post-scan impact speedup: 9.55x
- average conservative post-scan investigation speedup: 8.77x
- first-run scan cost reduction: 0% claimed; Atlas adds scan time, then produces reusable graph/context artifacts.
- scan cost reduction for repeated analysis: measured as avoided repeated manual context assembly, not as avoided repository scan time.
