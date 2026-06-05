# Phase 167 — Token Economics

| Repo | Claude 20Q | Atlas 20Q | Avg Claude | Avg Atlas | Savings% | Claude q/1k tok | Atlas q/1k tok |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| FastAPI | 17550 | 22031 | 878 | 1102 | -25.5% | 2.564 | 3.686 |
| Django | 17550 | 23325 | 878 | 1166 | -32.9% | 3.179 | 3.331 |
| VS Code | 17550 | 47379 | 878 | 2369 | -170.0% | 1.846 | 1.714 |
| Home Assistant | 17550 | 31930 | 878 | 1596 | -81.9% | 1.823 | 2.574 |

**Note:** Claude Alone token estimates include cumulative re-paste overhead (+20 tokens/question after Q3). Atlas adds export tokens but reduces Claude output length (~300 vs ~650 tokens).

## Quality-adjusted token efficiency

`quality_score_sum / total_tokens × 1000`

| Repo | Claude q/1k tok | Atlas q/1k tok | Winner |
| --- | ---: | ---: | --- |
| FastAPI | 2.564 | 3.686 | Atlas (+44%) |
| Django | 3.179 | 3.331 | Atlas (+5%) |
| VS Code | 1.846 | 1.714 | Claude Alone (-7%) |
| Home Assistant | 1.823 | 2.574 | Atlas (+41%) |

**Conclusion:** Multi-question sessions do **not** reduce raw token spend. They **do** improve quality-per-token on 3/4 repos. VS Code is the exception — large export payloads (avg 2,369 tokens/question) outweigh quality gains on a per-token basis, though quality still wins absolutely (+2.44).