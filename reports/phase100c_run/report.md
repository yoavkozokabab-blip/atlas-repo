# Historical Bug Replay Report

Program: phase100c-first-batch
Cases: 10

## Aggregate classifications

| Bucket | Buggy revision | Fixed revision |
|--------|---------------:|---------------:|
| `detected` | 0 | 0 |
| `strong_suspect` | 0 | 0 |
| `review_lead` | 0 | 0 |
| `refuted` | 8 | 8 |
| `unknown` | 0 | 0 |

## Case-level detected summary

- cases with detected on buggy: 0
- cases with detected on fixed: 0
- cases with detected on buggy only: 0
- detected case recall: 0.0
- detected case false-positive rate: 0.0
- detected case purity: None

## Per-case results

- `hold_black_executor`: buggy detected=False fixed detected=False
- `hold_pysnooper_encoding`: buggy detected=False fixed detected=False
- `hold_tqdm_enumerate`: buggy detected=False fixed detected=False
- `dist_off_by_one`: buggy detected=False fixed detected=False
- `dist_wrong_operator`: buggy detected=False fixed detected=False
- `dist_missing_base_case`: buggy detected=False fixed detected=False
- `neg_optional_by_design`: buggy detected=False fixed detected=False
- `neg_dominating_guard`: buggy detected=False fixed detected=False
- `neg_raise_only_exit`: buggy detected=False fixed detected=False
- `neg_expected_negative_test`: buggy detected=False fixed detected=False
