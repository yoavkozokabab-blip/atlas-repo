# Phase 152B Reliability Summary

Attempted: 23

Completed measured scans: 22

Timeouts: 1

| Repo | Status | Scan success | Timeout | Zero modules | Partial graph | Degraded | Scan sec |
| --- | --- | --- | --- | --- | --- | --- | --- |
| airflow | measured | True | False | False | False | False | 87.6 |
| aspnet_example | measured | True | False | False | False | False | 0.139 |
| atlas_self | timeout | False | True | True | True | True | None |
| celery | measured | True | False | False | False | False | 5.282 |
| django | measured | True | False | False | False | False | 21.467 |
| fastapi | measured | True | False | False | False | False | 2.934 |
| flask | measured | True | False | False | False | False | 0.661 |
| gin | measured | True | False | True | False | False | 0.035 |
| home_assistant | measured | True | False | False | False | False | 494.804 |
| kubernetes | measured | True | False | False | False | False | 4.398 |
| langchain | measured | True | False | False | False | False | 26.603 |
| nestjs | measured | True | False | False | False | False | 3.218 |
| nextjs | measured | True | False | False | False | False | 42.851 |
| pydantic | measured | True | False | False | False | False | 7.096 |
| qdrant | measured | True | False | False | False | False | 0.946 |
| react | measured | True | False | False | False | False | 6.3 |
| requests | measured | True | False | False | False | False | 0.509 |
| rich | measured | True | False | False | False | False | 2.787 |
| spring_boot_example | measured | True | False | True | False | False | 0.061 |
| turborepo | measured | True | False | False | False | False | 1.603 |
| typeorm | measured | True | False | False | False | False | 2.362 |
| typer | measured | True | False | False | False | False | 1.509 |
| vscode | measured | True | False | False | False | False | 33.238 |

Measurement caveat: an access-denied Python process tree from an interrupted prior test run was still visible before this campaign; timing should be treated as conservative/noisy if CPU contention occurred.
