# Real Repository Validation Report

Report schema: 1

## Frozen Candidate
- commit: b2871fafeeacbe247117ef4a8d68027580429a68
- flags: {"CROSS_FILE_CONSUMPTION_ENABLED": false, "CROSS_FILE_ENABLED": true, "INTERPROC_PROMOTION_ENABLED": true}
- real-repository verdict kinds: ['data_flow', 'security', 'semantic', 'value_flow']

## External Alpha Verdict
**HOLD**

## Corpus Composition
- repositories scanned: 24
- primary eligible repositories: 24/24
- tracks: {'primary': 24}
- historical bug cases: 0 across 0 repositories

## Readiness Gates
| gate | pass | detail |
| --- | --- | --- |
| unsafe_outcomes | True | 0 unsafe: [] |
| crash_free_completion | True | 24/24 completed (1.0) |
| primary_repository_count | True | 24/24 |
| historical_bug_cases | False | 0 cases across 0 repositories |
| review_completion | False | 300 unreviewed |
| adjudication_completion | True | 0 need adjudication |
| strict_precision | False | None from 0 reviewed findings |
| misleading_rate | False | None from 0 reviewed findings |
| repository_usefulness | False | median None; 0/24 primary repositories scored |
| would_use_again | False | None |
| review_lead_rate | False | None |

## Operational Safety
| repo | outcome | parse errors | modified tracked files | duration s |
| --- | --- | ---: | ---: | ---: |
| attrs | success | 0 | 0 | 6.922 |
| black | degraded | 5 | 0 | 18.253 |
| blinker | success | 0 | 0 | 0.606 |
| cachetools | success | 0 | 0 | 1.923 |
| celery | success | 0 | 0 | 45.014 |
| click | success | 0 | 0 | 9.03 |
| cookiecutter | degraded | 2 | 0 | 3.812 |
| dash | success | 0 | 0 | 27.028 |
| fastapi | success | 0 | 0 | 36.066 |
| flask | success | 0 | 0 | 7.744 |
| httpx | success | 0 | 0 | 8.966 |
| humanize | success | 0 | 0 | 1.206 |
| itsdangerous | success | 0 | 0 | 0.843 |
| marshmallow | success | 0 | 0 | 9.278 |
| pathspec | success | 0 | 0 | 1.707 |
| pluggy | success | 0 | 0 | 2.321 |
| pytest | success | 0 | 0 | 42.733 |
| requests | success | 0 | 0 | 4.957 |
| rich | success | 0 | 0 | 16.645 |
| sphinx | success | 0 | 0 | 66.695 |
| starlette | success | 0 | 0 | 10.088 |
| typer | success | 0 | 0 | 9.566 |
| wagtail | success | 0 | 0 | 116.951 |
| werkzeug | success | 0 | 0 | 14.61 |

## Finding Inventory
- total findings: 16110
- grounded verdict-eligible findings: 8832
- advisory findings: 7278
- grounded kinds: {'data_flow': 13, 'security': 412, 'semantic': 13, 'value_flow': 8394}
- advisory kinds: {'pattern': 7278}

## Precision
- reviewed in scope: 0
- unreviewed: 300
- needs adjudication: 0
- confirmed actionable: 0
- useful review lead: 0
- benign or intended: 0
- misleading: 0
- undecidable: 0
- strict precision: None
- weighted strict precision: None
- review-lead rate: None
- misleading rate: None

### Precision By Rule
| rule | confirmed | in scope | precision |
| --- | ---: | ---: | ---: |

_Advisory findings are separate from precision: 7278 total._

## Usefulness
- scored findings: 0
- mean finding usefulness: None
- median repository usefulness: None
- would use again: 0/0

> QuixBugs and holdout results remain separate regression gates. They are not blended into real-repository precision.
