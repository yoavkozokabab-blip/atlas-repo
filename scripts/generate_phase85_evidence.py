"""Generate Phase 85 evidence JSON artifacts (read-only benchmark pass).

Does not modify analyzer behavior. Writes:
  reports/phase85_rule_matrix.json
  reports/phase85_false_negative_inventory.json
  reports/phase85_false_positive_inventory.json
"""

from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from builder_core.benchmark import (  # noqa: E402
    NON_ALGORITHM_FILES,
    _is_algorithm_pair,
    _read_text,
    _semantic_findings,
    _test_documents,
)
from builder_core.external_benchmark import evaluate_holdout  # noqa: E402
from builder_core.python_analysis import analyze_python  # noqa: E402

REPORTS = _ROOT / "reports"
QUIXBUGS = Path(r"C:\Repos\QuixBugs")

RULE_CATALOG: List[Dict[str, Any]] = [
    {
        "rule": "bfs_queue_exhaustion",
        "source_location": "builder_core/semantic_reasoning.py:199 (_bfs_findings)",
        "algorithm_family": "bfs",
        "suspected_benchmark_coupling": "high",
        "coupling_notes": "Requires bfs profile; enriched by QuixBugs python_testcases stem match",
        "related_files_functions": ["breadth_first_search.py:breadth_first_search", "transfer_bfs_empty_queue/buggy.py:bfs"],
    },
    {
        "rule": "bfs_frontier_termination",
        "source_location": "builder_core/semantic_reasoning.py:213 (_bfs_findings)",
        "algorithm_family": "bfs",
        "suspected_benchmark_coupling": "medium",
        "coupling_notes": "Requires bfs profile and popleft without queue truthiness in while test",
        "related_files_functions": ["any bfs-profile function with non-standard loop guard"],
    },
    {
        "rule": "bfs_fifo_violation",
        "source_location": "builder_core/semantic_reasoning.py:225 (_bfs_findings)",
        "algorithm_family": "bfs",
        "suspected_benchmark_coupling": "low",
        "coupling_notes": "Queue pop() without popleft() on named queue/deque",
        "related_files_functions": ["bfs-profile functions using stack-style pop"],
    },
    {
        "rule": "bfs_missing_visited_tracking",
        "source_location": "builder_core/semantic_reasoning.py:237 (_bfs_findings)",
        "algorithm_family": "bfs",
        "suspected_benchmark_coupling": "medium",
        "coupling_notes": "Append to frontier without seen/visited identifier name",
        "related_files_functions": ["breadth_first_search.py", "transfer_bfs_empty_queue/*.py:bfs"],
    },
    {
        "rule": "bfs_cycle_handling",
        "source_location": "builder_core/semantic_reasoning.py:249 (_bfs_findings)",
        "algorithm_family": "bfs",
        "suspected_benchmark_coupling": "medium",
        "coupling_notes": "Visited name present but no in/not-in membership filter on frontier growth",
        "related_files_functions": ["bfs-profile functions with visited set naming"],
    },
    {
        "rule": "recursive_interval_not_shrinking",
        "source_location": "builder_core/semantic_reasoning.py:353 (_recursive_findings)",
        "algorithm_family": "binary_search",
        "suspected_benchmark_coupling": "very_high",
        "coupling_notes": "Function name binsearch AND file stem find_in_sorted",
        "related_files_functions": ["find_in_sorted.py:binsearch"],
    },
    {
        "rule": "recursive_euclidean_state_not_rotated",
        "source_location": "builder_core/semantic_reasoning.py:369 (_recursive_findings)",
        "algorithm_family": "gcd",
        "suspected_benchmark_coupling": "high",
        "coupling_notes": "Function name gcd with recursive second arg literally b",
        "related_files_functions": ["gcd.py:gcd", "transfer_gcd_no_rotate/buggy.py:gcd"],
    },
    {
        "rule": "recursive_singleton_base_case_missing",
        "source_location": "builder_core/semantic_reasoning.py:385 (_recursive_findings)",
        "algorithm_family": "merge_sort",
        "suspected_benchmark_coupling": "very_high",
        "coupling_notes": "Function name mergesort only",
        "related_files_functions": ["mergesort.py:mergesort"],
    },
    {
        "rule": "recursive_empty_choice_base_case_missing",
        "source_location": "builder_core/semantic_reasoning.py:415 (_recursive_findings)",
        "algorithm_family": "coin_change",
        "suspected_benchmark_coupling": "very_high",
        "coupling_notes": "Function name possible_change only",
        "related_files_functions": ["possible_change.py:possible_change"],
    },
    {
        "rule": "recursive_identity_base_case",
        "source_location": "builder_core/semantic_reasoning.py:437 (_recursive_findings)",
        "algorithm_family": "subsequences",
        "suspected_benchmark_coupling": "very_high",
        "coupling_notes": "Function name subsequences with k==0 empty list return",
        "related_files_functions": ["subsequences.py:subsequences"],
    },
    {
        "rule": "dijkstra_relaxes_from_destination",
        "source_location": "builder_core/semantic_reasoning.py:486 (_shortest_path_findings)",
        "algorithm_family": "shortest_path_dijkstra",
        "suspected_benchmark_coupling": "very_high",
        "coupling_notes": "Function shortest_path_length; variables length_by_edge and .get()",
        "related_files_functions": ["shortest_path_length.py:shortest_path_length"],
    },
    {
        "rule": "floyd_warshall_recurrence_direction",
        "source_location": "builder_core/semantic_reasoning.py:515 (_shortest_path_findings)",
        "algorithm_family": "shortest_path_floyd_warshall",
        "suspected_benchmark_coupling": "very_high",
        "coupling_notes": "Function shortest_path_lengths; indices i,j,k and length_by_path",
        "related_files_functions": ["shortest_path_lengths.py:shortest_path_lengths"],
    },
    {
        "rule": "bellman_ford_updates_edge_weight",
        "source_location": "builder_core/semantic_reasoning.py:541 (_shortest_path_findings)",
        "algorithm_family": "shortest_path_bellman_ford",
        "suspected_benchmark_coupling": "very_high",
        "coupling_notes": "Function shortest_paths; assigns min() into weight_by_edge subscript",
        "related_files_functions": ["shortest_paths.py:shortest_paths"],
    },
    {
        "rule": "counting_sort_reconstructs_from_input",
        "source_location": "builder_core/semantic_reasoning.py:582 (_sorting_cardinality_findings)",
        "algorithm_family": "sorting_counting",
        "suspected_benchmark_coupling": "very_high",
        "coupling_notes": "Function bucketsort; enumerate(arr) reconstruction pattern",
        "related_files_functions": ["bucketsort.py:bucketsort"],
    },
    {
        "rule": "heap_window_reprocesses_seed",
        "source_location": "builder_core/semantic_reasoning.py:612 (_sorting_cardinality_findings)",
        "algorithm_family": "sorting_heap",
        "suspected_benchmark_coupling": "very_high",
        "coupling_notes": "Function kheapsort; arr[:k] seed plus full arr iteration",
        "related_files_functions": ["kheapsort.py:kheapsort"],
    },
    {
        "rule": "quicksort_drops_duplicate_values",
        "source_location": "builder_core/semantic_reasoning.py:638 (_sorting_cardinality_findings)",
        "algorithm_family": "sorting_quicksort",
        "suspected_benchmark_coupling": "very_high",
        "coupling_notes": "Function quicksort; strict x/pivot comparisons",
        "related_files_functions": ["quicksort.py:quicksort"],
    },
    {
        "rule": "recursive_progress_invariant",
        "source_location": "builder_core/semantic_reasoning.py:674 (_generic_profile_findings)",
        "algorithm_family": "recursion_generic",
        "suspected_benchmark_coupling": "low",
        "coupling_notes": "Recursion profile; no visible if/return base case in AST",
        "related_files_functions": ["any function matching recursion profile patterns"],
    },
    {
        "rule": "graph_traversal_cycle_handling",
        "source_location": "builder_core/semantic_reasoning.py:692 (_generic_profile_findings)",
        "algorithm_family": "graph_traversal",
        "suspected_benchmark_coupling": "medium",
        "coupling_notes": "dfs or graph_traversal profile; append without visited name",
        "related_files_functions": ["depth_first_search.py (FN)", "transfer_bfs_empty_queue/*.py:bfs"],
    },
]

FALSE_NEGATIVE_INVENTORY: List[Dict[str, Any]] = [
    {"file": "bitcount.py", "actual_bug_summary": "Uses n ^= n - 1 instead of n &= n - 1; bit-clearing loop wrong.", "likely_required_reasoning_type": "Numerical loop-state progress for Kernighan-style bit counting", "candidate_subsystem": "numerical_bitwise_reasoning"},
    {"file": "depth_first_search.py", "actual_bug_summary": "Omits nodesvisited.add(node) before recursive expansion; cycles recurse indefinitely.", "likely_required_reasoning_type": "Graph traversal: mark expanded node before recursive descent", "candidate_subsystem": "dfs_visited_state"},
    {"file": "detect_cycle.py", "actual_bug_summary": "Dereferences hare.successor without null guard on acyclic lists.", "likely_required_reasoning_type": "Linked-list traversal null-guard analysis", "candidate_subsystem": "pointer_null_guard"},
    {"file": "find_first_in_sorted.py", "actual_bug_summary": "while lo <= hi with hi=len(arr) exclusive allows arr[len(arr)] access.", "likely_required_reasoning_type": "Inclusive vs exclusive interval boundary reasoning", "candidate_subsystem": "iterative_binary_search_boundaries"},
    {"file": "flatten.py", "actual_bug_summary": "Scalar leaves yield flatten(x) generators instead of yielding x.", "likely_required_reasoning_type": "Recursive tree traversal: emit scalars, recurse containers only", "candidate_subsystem": "generator_leaf_shape"},
    {"file": "get_factors.py", "actual_bug_summary": "Returns [] when no smaller divisor; loses residual prime factor.", "likely_required_reasoning_type": "Terminal-state: emit remaining prime when search exhausts", "candidate_subsystem": "factorization_terminal_state"},
    {"file": "hanoi.py", "actual_bug_summary": "Main move emits (start, helper) instead of (start, end).", "likely_required_reasoning_type": "Recursive planning with source/helper/destination roles", "candidate_subsystem": "hanoi_recurrence"},
    {"file": "is_valid_parenthesization.py", "actual_bug_summary": "Returns True when unmatched opens leave positive final depth.", "likely_required_reasoning_type": "Stack-depth validation; final depth must be zero", "candidate_subsystem": "delimiter_stack_invariant"},
    {"file": "knapsack.py", "actual_bug_summary": "Uses weight < j instead of weight <= j; excludes exact-fit items.", "likely_required_reasoning_type": "DP transition boundary / exact-fit inclusion", "candidate_subsystem": "dp_boundary_reasoning"},
    {"file": "kth.py", "actual_bug_summary": "Upper partition keeps k unchanged instead of rebasing rank.", "likely_required_reasoning_type": "Selection partition rank rebasing invariant", "candidate_subsystem": "selection_rank_rebasing"},
    {"file": "lcs_length.py", "actual_bug_summary": "Match uses dp[i-1,j]+1 instead of diagonal dp[i-1,j-1]+1.", "likely_required_reasoning_type": "Paired-sequence DP: match advances both axes", "candidate_subsystem": "paired_sequence_dp"},
    {"file": "levenshtein.py", "actual_bug_summary": "Equal leading characters incorrectly add edit cost.", "likely_required_reasoning_type": "Edit-distance: equal chars advance both at zero cost", "candidate_subsystem": "paired_sequence_dp"},
    {"file": "lis.py", "actual_bug_summary": "Assigns longest = length + 1 allowing global optimum to decrease.", "likely_required_reasoning_type": "DP aggregate monotonicity invariant", "candidate_subsystem": "dp_monotonicity"},
    {"file": "longest_common_subsequence.py", "actual_bug_summary": "On match advances a but not b; reuses same b character.", "likely_required_reasoning_type": "Matched-symbol recursion consumes both sequences", "candidate_subsystem": "paired_sequence_consumption"},
    {"file": "max_sublist_sum.py", "actual_bug_summary": "Carries negative prefixes instead of restart/clamp (Kadane).", "likely_required_reasoning_type": "Kadane restart-vs-extend recurrence", "candidate_subsystem": "kadane_recurrence"},
    {"file": "minimum_spanning_tree.py", "actual_bug_summary": "Updates component sets without shared merged representative.", "likely_required_reasoning_type": "Union-find equivalence-class consistency", "candidate_subsystem": "union_find_consistency"},
    {"file": "next_palindrome.py", "actual_bug_summary": "Overflow multiplies by len(digit_list) not len-1; extra zero.", "likely_required_reasoning_type": "Numeric carry expansion shape invariant", "candidate_subsystem": "output_shape_boundary"},
    {"file": "next_permutation.py", "actual_bug_summary": "Swap comparison reversed; selects smaller not greater successor.", "likely_required_reasoning_type": "Next-permutation comparison direction", "candidate_subsystem": "next_permutation_profile"},
    {"file": "pascal.py", "actual_bug_summary": "Row r built with range(0,r) not range(0,r+1); drops right edge.", "likely_required_reasoning_type": "Combinatorial row has r+1 entries", "candidate_subsystem": "output_shape_boundary"},
    {"file": "powerset.py", "actual_bug_summary": "Returns only include branch; omits exclude branch.", "likely_required_reasoning_type": "Include/exclude branch completeness; cardinality 2**n", "candidate_subsystem": "recursive_branch_completeness"},
    {"file": "reverse_linked_list.py", "actual_bug_summary": "Never sets prevnode=node; reversed prefix lost, result None.", "likely_required_reasoning_type": "Loop-carried pointer state for list reversal", "candidate_subsystem": "linked_list_loop_state"},
    {"file": "rpn_eval.py", "actual_bug_summary": "Pops operands in wrong order for subtraction/division.", "likely_required_reasoning_type": "Stack machine operand roles (second pop is left)", "candidate_subsystem": "stack_machine_operands"},
    {"file": "shunting_yard.py", "actual_bug_summary": "Never pushes operators onto opstack; operators disappear.", "likely_required_reasoning_type": "Parser token conservation on operator stack", "candidate_subsystem": "parser_token_conservation"},
    {"file": "sieve.py", "actual_bug_summary": "Uses any(n%p>0) not all-divisors; empty-prime edge case.", "likely_required_reasoning_type": "Prime sieve quantifier and vacuous truth", "candidate_subsystem": "domain_quantifier_reasoning"},
    {"file": "sqrt.py", "actual_bug_summary": "Checks abs(x-approx) not abs(x-approx**2) for convergence.", "likely_required_reasoning_type": "Newton method residual invariant", "candidate_subsystem": "numerical_method_residual"},
    {"file": "to_base.py", "actual_bug_summary": "Appends LSD to right; digit order reversed.", "likely_required_reasoning_type": "Base conversion prepend-or-reverse invariant", "candidate_subsystem": "numeric_conversion_direction"},
    {"file": "topological_ordering.py", "actual_bug_summary": "Checks outgoing order not incoming prerequisites.", "likely_required_reasoning_type": "Topological dependency direction invariant", "candidate_subsystem": "topological_dependency_direction"},
    {"file": "wrap.py", "actual_bug_summary": "Fails to append final unsplit remainder after loop.", "likely_required_reasoning_type": "Segmentation remainder consumption", "candidate_subsystem": "segmentation_remainder"},
]


def _evaluate_quixbugs_pairs(project: Path) -> tuple[list[dict], list[dict]]:
    root = project.expanduser().resolve()
    buggy_root = root / "python_programs"
    correct_root = root / "correct_python_programs"
    tests = _test_documents(root)
    buggy_paths = {p.name: p for p in buggy_root.glob("*.py") if p.is_file()}
    correct_paths = {p.name: p for p in correct_root.glob("*.py") if p.is_file()}
    paired = [n for n in sorted(set(buggy_paths) & set(correct_paths)) if _is_algorithm_pair(n)]

    buggy_results: list[dict] = []
    correct_results: list[dict] = []
    for name in paired:
        buggy_rel = buggy_paths[name].relative_to(root).as_posix()
        correct_rel = correct_paths[name].relative_to(root).as_posix()
        buggy_analysis = analyze_python(buggy_rel, _read_text(buggy_paths[name]), test_documents=tests)
        correct_analysis = analyze_python(correct_rel, _read_text(correct_paths[name]), test_documents=tests)
        buggy_results.append({"path": buggy_rel, "file": name, "findings": _semantic_findings(buggy_analysis)})
        correct_results.append({"path": correct_rel, "file": name, "findings": _semantic_findings(correct_analysis)})
    return buggy_results, correct_results


def _count_by_rule(results: list[dict]) -> Counter:
    counts: Counter = Counter()
    for item in results:
        for finding in item["findings"]:
            counts[finding["rule"]] += 1
    return counts


def _build_rule_matrix(quix_buggy: list[dict], quix_correct: list[dict], holdout: dict) -> dict:
    quix_tp = _count_by_rule([x for x in quix_buggy if x["findings"]])
    quix_fp = _count_by_rule([x for x in quix_correct if x["findings"]])
    hold_buggy = holdout.get("buggy_results", [])
    hold_correct = holdout.get("correct_results", [])
    hold_tp = _count_by_rule([x for x in hold_buggy if x["findings"]])
    hold_fp = _count_by_rule([x for x in hold_correct if x["findings"]])

    rules_out = []
    for meta in RULE_CATALOG:
        rule = meta["rule"]
        rules_out.append(
            {
                "rule": rule,
                "source_location": meta["source_location"],
                "algorithm_family": meta["algorithm_family"],
                "quixbugs_tp_count": quix_tp.get(rule, 0),
                "quixbugs_fp_count": quix_fp.get(rule, 0),
                "holdout_tp_count": hold_tp.get(rule, 0),
                "holdout_fp_count": hold_fp.get(rule, 0),
                "suspected_benchmark_coupling": meta["suspected_benchmark_coupling"],
                "coupling_notes": meta["coupling_notes"],
                "related_files_functions": meta["related_files_functions"],
            }
        )
    return {
        "generated_at": "2026-05-30",
        "generator": "scripts/generate_phase85_evidence.py",
        "benchmarks": {
            "quixbugs": {"project": str(QUIXBUGS), "algorithm_pairs": len(quix_buggy)},
            "holdout": {"pairs_root": holdout.get("pairs_root", ""), "cases": holdout.get("cases_analyzed", 0)},
        },
        "summary": {
            "total_rules": len(rules_out),
            "quixbugs_tp_files": sum(1 for x in quix_buggy if x["findings"]),
            "quixbugs_fp_files": sum(1 for x in quix_correct if x["findings"]),
            "holdout_tp_files": sum(1 for x in hold_buggy if x["findings"]),
            "holdout_fp_files": sum(1 for x in hold_correct if x["findings"]),
        },
        "rules": rules_out,
    }


def _build_fn_inventory(quix_buggy: list[dict]) -> dict:
    missed = [x for x in quix_buggy if not x["findings"]]
    entries = []
    fn_by_file = {item["file"]: item for item in FALSE_NEGATIVE_INVENTORY}
    for item in missed:
        meta = fn_by_file.get(item["file"], {})
        entries.append(
            {
                "benchmark": "quixbugs",
                "file": item["file"],
                "path": item["path"],
                "actual_bug_summary": meta.get("actual_bug_summary", ""),
                "likely_required_reasoning_type": meta.get("likely_required_reasoning_type", ""),
                "candidate_subsystem": meta.get("candidate_subsystem", ""),
            }
        )
    return {
        "generated_at": "2026-05-30",
        "benchmark": "quixbugs",
        "total_false_negatives": len(entries),
        "entries": entries,
    }


def _build_fp_inventory(quix_correct: list[dict], holdout: dict) -> dict:
    entries: list[dict] = []

    for item in quix_correct:
        if not item["findings"]:
            continue
        for finding in item["findings"]:
            entries.append(
                {
                    "benchmark": "quixbugs",
                    "file": item["file"],
                    "path": item["path"],
                    "rule": finding["rule"],
                    "line": finding.get("line"),
                    "why_it_fired": finding.get("message", ""),
                    "why_fixed_code_is_valid": "Paired QuixBugs corrected implementation passes tests; no semantic violation expected.",
                    "evidence": finding.get("evidence", ""),
                }
            )

    hold_correct = holdout.get("correct_results", [])
    hold_buggy = {x["case_id"]: x for x in holdout.get("buggy_results", [])}
    fp_explanations = {
        "bfs_missing_visited_tracking": {
            "why_it_fired": "Rule requires a seen/visited identifier when appending to BFS frontier; fixed code uses while queue with append-only expansion and no visited name.",
            "why_fixed_code_is_valid": "Correct minimal BFS on acyclic/small graphs can omit explicit visited tracking; loop terminates on empty queue and returns False when goal unreachable.",
        },
        "graph_traversal_cycle_handling": {
            "why_it_fired": "Function matches graph_traversal profile (neighbor/graph tokens) and appends to frontier without visited identifier.",
            "why_fixed_code_is_valid": "Same valid BFS: uses proper while queue termination; acyclic test graphs do not require visited set for correctness in holdout fixture.",
        },
    }
    for item in hold_correct:
        if not item["findings"]:
            continue
        buggy = hold_buggy.get(item["case_id"], {})
        for finding in item["findings"]:
            rule = finding["rule"]
            expl = fp_explanations.get(rule, {})
            entries.append(
                {
                    "benchmark": "holdout",
                    "case_id": item["case_id"],
                    "file": item["path"],
                    "rule": rule,
                    "line": finding.get("line"),
                    "why_it_fired": expl.get("why_it_fired", finding.get("message", "")),
                    "why_fixed_code_is_valid": expl.get(
                        "why_fixed_code_is_valid",
                        "Holdout fixed pair is ground-truth correct implementation.",
                    ),
                    "evidence": finding.get("evidence", ""),
                    "paired_buggy_rules": [f["rule"] for f in buggy.get("findings", [])],
                }
            )

    return {
        "generated_at": "2026-05-30",
        "total_false_positives": len(entries),
        "total_false_positive_files": len({(e["benchmark"], e.get("file", e.get("case_id"))) for e in entries}),
        "entries": entries,
    }


def main() -> int:
    if not QUIXBUGS.is_dir():
        print(f"ERROR: QuixBugs not found at {QUIXBUGS}", file=sys.stderr)
        return 1

    quix_buggy, quix_correct = _evaluate_quixbugs_pairs(QUIXBUGS)
    holdout = evaluate_holdout()

    REPORTS.mkdir(parents=True, exist_ok=True)
    paths = {
        "rule_matrix": REPORTS / "phase85_rule_matrix.json",
        "false_negative_inventory": REPORTS / "phase85_false_negative_inventory.json",
        "false_positive_inventory": REPORTS / "phase85_false_positive_inventory.json",
    }

    artifacts = {
        paths["rule_matrix"]: _build_rule_matrix(quix_buggy, quix_correct, holdout),
        paths["false_negative_inventory"]: _build_fn_inventory(quix_buggy),
        paths["false_positive_inventory"]: _build_fp_inventory(quix_correct, holdout),
    }

    for path, payload in artifacts.items():
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        print(f"wrote {path}")

    matrix = artifacts[paths["rule_matrix"]]
    print(f"rules: {matrix['summary']['total_rules']}")
    print(f"quixbugs FN files: {matrix['summary']['quixbugs_tp_files']} TP, {40 - matrix['summary']['quixbugs_tp_files']} FN")
    print(f"holdout FP files: {matrix['summary']['holdout_fp_files']}")
    print(f"fp inventory entries: {artifacts[paths['false_positive_inventory']]['total_false_positives']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
