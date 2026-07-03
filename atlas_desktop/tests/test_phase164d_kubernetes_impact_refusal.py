"""Phase 164D — Kubernetes impact refusal on shallow/unsupported graphs.

Trust Audit v2 P-KU-01..06 must refuse impact (ok=false) when the repository has
~25k files but only a handful of Python modules and no Go import graph.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import pytest

from atlas_desktop.impact_engine.engine import analyze_impact

K8S_MODULES = [
    "hack/boilerplate/boilerplate.py",
    "hack/verify-flags-underscore.py",
    "staging/src/k8s.io/kubectl/pkg/util/i18n/translations/extract.py",
]

K8S_SCAN = {
    "file_count": 24860,
    "module_count": 3,
    "dependency_edges": 0,
    "graph_scope": "entire_repo",
    "degraded": True,
}

# Canonical Trust Audit v2 impact targets (reports/phase164b_audit_normalization.md)
K8S_IMPACT_TARGETS = [
    "pkg/kubelet/kubelet.go",
    "pkg/scheduler/scheduler.go",
    "pkg/controller/deployment/deployment_controller.go",
    "staging/src/k8s.io/apiserver/pkg/admission/plugin/webhook/validating/dispatcher.go",
    "staging/src/k8s.io/apiserver/pkg/audit/request.go",
    "staging/src/k8s.io/apiextensions-apiserver/pkg/apis/apiextensions/validation/validation.go",
]


def _k8s_state(*, with_symbol_pollution: bool = True):
    """Synthetic Kubernetes scan: many files, 3 Python modules, zero import edges."""
    nodes = [
        {"id": f"n{i}", "type": "module", "path": p, "fan_in": 0,
         "dotted": p.replace("/", ".").rstrip(".py")}
        for i, p in enumerate(K8S_MODULES)
    ]
    evidence_store = {}
    if with_symbol_pollution:
        # Mimics audit pollution: validation/argparse symbols that previously
        # let P-KU-06 resolve via generic concept matching.
        evidence_store = {
            "symbol_index": {
                "project_root": "/kubernetes",
                "files": {
                    "hack/boilerplate/boilerplate.py": {
                        "symbols": [
                            {"name": "ArgumentParser", "qualname": "ArgumentParser",
                             "file_path": "hack/boilerplate/boilerplate.py", "line": 1, "kind": "class"},
                            {"name": "validate", "qualname": "validate",
                             "file_path": "hack/boilerplate/boilerplate.py", "line": 2, "kind": "function"},
                        ],
                        "imports": ["argparse"],
                        "calls": [],
                    },
                },
            },
        }
    return {
        "graph": {"nodes": nodes, "edges": []},
        "index": {"files": [{"path": p} for p in K8S_MODULES]},
        "scan": dict(K8S_SCAN),
        "evidence_store": evidence_store,
    }


@pytest.mark.parametrize("target", K8S_IMPACT_TARGETS)
def test_kubernetes_impact_targets_refuse(target):
    result = analyze_impact(target, _k8s_state())
    assert result["ok"] is False, f"Expected refusal for {target}, got ok=True"
    assert result.get("status") in ("target_not_resolved", "unsupported_language_limited")
    assert result.get("confidence") == "low"
    assert result.get("direct_impact") == []
    assert result.get("indirect_impact") == []
    assert result.get("affected_files") == []
    assert not result.get("affected_file_count")
    assert "shallow" in (result.get("message") or result.get("reason") or "").lower() or \
           "graph" in (result.get("message") or result.get("reason") or "").lower()


def test_p_ku_06_validation_path_does_not_fake_resolve():
    """Regression: validation.go must not resolve to hack/boilerplate via concept lexicon."""
    target = K8S_IMPACT_TARGETS[5]
    result = analyze_impact(target, _k8s_state(with_symbol_pollution=True))
    assert result["ok"] is False
    assert result.get("status") in ("target_not_resolved", "unsupported_language_limited")
    affected = result.get("affected_files") or []
    assert "hack/boilerplate/boilerplate.py" not in affected
    assert "argumentparser" not in [str(x).lower() for x in affected]


def test_shallow_graph_exact_path_without_edges_still_refuses():
    """Even an indexed Python path refuses when there are no import/symbol edges."""
    state = _k8s_state(with_symbol_pollution=False)
    result = analyze_impact("hack/boilerplate/boilerplate.py", state)
    assert result["ok"] is False
    assert result.get("confidence") == "low"


def test_healthy_graph_still_allows_semantic_resolution():
    """Guard must not break normal Python repos with full graphs."""
    paths = ["api/routes.py", "services/auth.py", "core/hub.py"]
    nodes = [
        {"id": f"n{i}", "type": "module", "path": p, "fan_in": 2}
        for i, p in enumerate(paths)
    ]
    edges = [{"type": "imports", "from": "n1", "to": "n0", "resolved": True}]
    state = {
        "graph": {"nodes": nodes, "edges": edges},
        "index": {"files": [{"path": p} for p in paths]},
        "scan": {"file_count": 300, "module_count": 73, "dependency_edges": 159},
        "evidence_store": {},
    }
    result = analyze_impact("api/routes.py", state)
    assert result["ok"] is True
    assert result.get("direct_impact") is not None
