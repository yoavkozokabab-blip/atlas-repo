# Overnight Token Savings

Token counts are estimates. The conservative no-Atlas baseline assumes a developer manually assembles focused context equal to 5% of repository source tokens, bounded to 8k-50k tokens, and never below the Atlas compact packet. This avoids claiming full-repository paste behavior.

| Repo | Source token estimate | Conservative no-Atlas context | Atlas verbose tokens | Atlas compact tokens | Compact vs verbose reduction | Conservative Atlas reduction |
|---|---:|---:|---:|---:|---:|---:|
| FastAPI | 956,323 | 47,816 | 421 | 325 | 22.80% | 99.32% |
| Django | 4,842,875 | 50,000 | 495 | 385 | 22.22% | 99.23% |
| Pydantic | 1,817,315 | 50,000 | 526 | 400 | 23.95% | 99.20% |
| LangChain | 3,158,806 | 50,000 | 552 | 407 | 26.27% | 99.19% |
| React | 5,472,648 | 50,000 | 700 | 480 | 31.43% | 99.04% |
| Qdrant | 3,608,089 | 50,000 | 905 | 489 | 45.97% | 99.02% |
| OpenBB | 2,570,502 | 50,000 | 732 | 520 | 28.96% | 98.96% |
| Next.js | 20,843,874 | 50,000 | 962 | 588 | 38.88% | 98.82% |
| NestJS | 845,486 | 42,274 | 708 | 522 | 26.27% | 98.77% |
| Home Assistant | 27,150,712 | 50,000 | 1,311 | 634 | 51.64% | 98.73% |
| VS Code | 32,428,795 | 50,000 | 1,185 | 674 | 43.12% | 98.65% |
| Rich | 421,786 | 21,089 | 451 | 359 | 20.40% | 98.30% |
| Typer | 253,631 | 12,681 | 453 | 355 | 21.63% | 97.20% |
| SQLModel | 165,636 | 8,281 | 439 | 332 | 24.37% | 95.99% |
| QuixBugs | 127,422 | 8,000 | 493 | 400 | 18.86% | 95.00% |
| Requests | 101,824 | 8,000 | 780 | 434 | 44.36% | 94.58% |
| Flask | 147,416 | 8,000 | 787 | 449 | 42.95% | 94.39% |

Average conservative context reduction: 97.91%
Average compact-vs-verbose reduction: 31.42%

Limit: this is context-size economics only. It does not prove answer quality by itself.
