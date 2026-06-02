# Real Repository Validation Report

Report schema: 1

## Frozen Candidate
- commit: e3b55a81c408ed4481ddf38eaed7b049079b6a0f
- flags: {"CROSS_FILE_CONSUMPTION_ENABLED": false, "CROSS_FILE_ENABLED": true, "INTERPROC_PROMOTION_ENABLED": true}
- real-repository verdict kinds: ['data_flow', 'security', 'semantic', 'value_flow']

## External Alpha Verdict
**HOLD**

## Corpus Composition
- repositories scanned: 2
- primary eligible repositories: 0/24
- tracks: {'pilot': 2}
- historical bug cases: 0 across 0 repositories

## Readiness Gates
| gate | pass | detail |
| --- | --- | --- |
| unsafe_outcomes | True | 0 unsafe: [] |
| crash_free_completion | True | 2/2 completed (1.0) |
| primary_repository_count | False | 0/24 |
| historical_bug_cases | False | 0 cases across 0 repositories |
| review_completion | True | 0 unreviewed |
| adjudication_completion | True | 0 need adjudication |
| strict_precision | False | 0.0 from 202 reviewed findings |
| misleading_rate | False | 0.0743 from 202 reviewed findings |
| repository_usefulness | False | median None; 0/0 primary repositories scored |
| would_use_again | False | None |
| review_lead_rate | True | 0.7327 |

## Operational Safety
| repo | outcome | parse errors | modified tracked files | duration s |
| --- | --- | ---: | ---: | ---: |
| openai-plugins-public-pilot | success | 0 | 0 | 12.749 |
| openai-skills-public-pilot | success | 0 | 0 | 3.738 |

## Finding Inventory
- total findings: 720
- grounded verdict-eligible findings: 202
- advisory findings: 518
- grounded kinds: {'security': 26, 'value_flow': 176}
- advisory kinds: {'pattern': 518}

## Precision
- reviewed in scope: 202
- unreviewed: 0
- needs adjudication: 0
- confirmed actionable: 0
- useful review lead: 148
- benign or intended: 34
- misleading: 15
- undecidable: 5
- strict precision: 0.0
- weighted strict precision: 0.0
- review-lead rate: 0.7327
- misleading rate: 0.0743

### Precision By Rule
| rule | confirmed | in scope | precision |
| --- | ---: | ---: | ---: |
| command_injection | 0 | 14 | 0.0 |
| null_dereference | 0 | 176 | 0.0 |
| path_traversal | 0 | 12 | 0.0 |

_Advisory findings are separate from precision: 518 total._

## Usefulness
- scored findings: 202
- mean finding usefulness: 2.4158
- median repository usefulness: None
- would use again: 0/0

> QuixBugs and holdout results remain separate regression gates. They are not blended into real-repository precision.
