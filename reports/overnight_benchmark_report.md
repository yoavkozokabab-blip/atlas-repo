# Overnight Benchmark Report

Generated: 2026-06-04T02:10:53

## Campaign Summary

- repositories attempted: 18
- repositories measured: 17
- failed/timeouts/unavailable: 1
- clone result: all requested GitHub repositories were cloned successfully; QuixBugs used existing C:\Repos\QuixBugs; Home Assistant used existing external_repos/home_assistant.
- Atlas source code changes: none performed by this campaign.

## Strongest Evidence

- Home Assistant: 9,709 modules, 36,013 edges, scan 494.804s, conservative context reduction 98.73%.
- Django: 929 modules, 2,915 edges, scan 21.467s, conservative context reduction 99.23%.
- FastAPI: 73 modules, 159 edges, scan 2.934s, conservative context reduction 99.32%.
- VS Code: 7,563 modules, 13,228 edges, scan 33.238s, conservative context reduction 98.65%.
- Requests: 20 modules, 66 edges, scan 0.509s, conservative context reduction 94.58%.

## Limitations

- Quality scores are deterministic proxy scores from Atlas outputs, not human-reviewed task success.
- No external LLM was called; LLM comparison is estimated from context size and conservative manual-review assumptions.
- Atlas self full-workspace scan timed out after 2400s; this remains visible as a performance failure.
- Rust-heavy Qdrant and benchmark-style QuixBugs produced weak/no dependency edges, so graph claims should be challenged there.
- LangChain produced many modules but zero resolved edges in this run, indicating graph coverage limitations for that layout.

## Improvement Opportunities

1. Add a safe self-repository benchmark scope for Atlas that excludes generated/runtime/external corpus folders without timing out.
2. Improve graph coverage for monorepos with namespace packages or nonstandard layouts, especially LangChain.
3. Add Rust/other-language graph support or clearly mark unsupported-language repositories such as Qdrant as partial.
4. Add human-reviewed quality scoring for the top repositories; current quality scores are proxy metrics.
5. Track direct evidence snippets for impact/investigation/build outputs so reports can grade specificity, not only successful API shape.
