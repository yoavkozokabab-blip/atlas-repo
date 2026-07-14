"""Benchmark #2 symbol slicing: file-level vs symbol-level tokens.

Usage: py -3 scripts/bench_symbol_slicing.py <repo_path> "<task>"
Reports pack tokens, file-vs-symbol tokens, reduction %, files sliced, time.
"""
import json
import os
import sys
import time

from verification_isolation import activate_isolated_atlas_data

activate_isolated_atlas_data("bench-symbol-slicing")

from atlas_desktop import api, context_pack as cp

repo = os.path.abspath(sys.argv[1])
task = sys.argv[2] if len(sys.argv) > 2 else "fix authentication timeout"

t0 = time.time()
r = api.scan_repository(repo, None)
scan_s = time.time() - t0
if not r.get("ok"):
    print(json.dumps({"repo": os.path.basename(repo), "error": r.get("error")}))
    raise SystemExit(0)

t1 = time.time()
pack = cp.build_context_pack_from_state(repo, task, dict(api._STATE), include_snippets=False, max_files=8)
build_s = time.time() - t1

recs = pack["recommended_files"]
agg = pack.get("symbol_slicing") or {}
# Sum full-file tokens across ALL selected files (the file-level baseline).
file_tokens_all = sum(int(it.get("full_token_estimate") or it.get("token_estimate") or 0) for it in recs)
print(json.dumps({
    "repo": os.path.basename(repo),
    "task": task,
    "files_in_index": r.get("file_count"),
    "scan_s": round(scan_s, 1),
    "build_s": round(build_s, 2),
    "confidence": pack["confidence"],
    "pack_markdown_tokens": pack["token_estimate"],
    "selected_files": len(recs),
    "files_sliced": agg.get("files_sliced", 0),
    "file_level_tokens_sliced_files": agg.get("file_level_tokens", 0),
    "symbol_level_tokens_sliced_files": agg.get("symbol_level_tokens", 0),
    "slice_reduction_pct": agg.get("token_reduction_pct", 0.0),
    "all_selected_file_tokens": file_tokens_all,
}, indent=2))
# Show a couple of concrete slices as evidence.
for it in recs:
    if it.get("symbol_slices"):
        print(f"  e.g. {it['path']}: file~{it['full_token_estimate']} -> symbols~{it['sliced_token_estimate']} (-{it['token_reduction_pct']}%)")
        for s in it["symbol_slices"][:3]:
            print(f"       {s['symbol']} ({s['kind']}) L{s['start_line']}-{s['end_line']} ~{s['token_estimate']}tok {s['confidence_label']}")
        break
