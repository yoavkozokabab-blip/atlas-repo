# Run Sets

`run_all.py` writes timestamped run sets here:

```text
results/run_sets/<run_set_id>/
  manifest.json
  manual_run_sheet.md
  pending_runs.jsonl
  runs/<condition>/*.json
```

Pending records are not benchmark results. They become valid only after a real
agent response is captured and scored.
