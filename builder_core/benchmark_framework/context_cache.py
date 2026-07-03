"""Phase 104D — cached expensive benchmark context stages."""

from __future__ import annotations

import hashlib
import json
import os
import time
from typing import Any, Dict, List, Optional

from . import FRAMEWORK_VERSION, SCHEMA_VERSION
from .compact_packets import COMPACT_INSTRUMENTATION_VERSION, packet_format_from_env
from .schema import dump_json, load_json

CACHE_VERSION = "phase104d-v1"
GRAPH_SCOPE = "production"

CACHED_STAGES = (
    "repository_understanding",
    "dependency_graph",
    "architectural_risk",
    "contract_facts",
    "verification_evidence",
)


def cache_enabled_from_env() -> bool:
    value = os.environ.get("Atlas_BENCHMARK_CONTEXT_CACHE", "").strip().lower()
    return value in {"1", "true", "yes", "on"}


def _cache_root(repo_path: str) -> str:
    return os.path.join(os.path.abspath(repo_path), ".atlas_builder", "benchmark_context_cache")


def compute_repo_fingerprint(
    repo_path: str,
    index: Optional[Dict[str, Any]] = None,
) -> str:
    """Fingerprint production-indexed files using path, mtime, and size."""
    root = os.path.abspath(repo_path)
    entries: List[str] = []
    if index and index.get("files"):
        for item in index.get("files", []):
            path = str(item.get("path", "")).replace("\\", "/")
            if not path:
                continue
            role = item.get("role") or ""
            category = item.get("category") or ""
            if role not in {"production_code", "test"} and category not in {"src", "test"}:
                continue
            if not path.endswith(".py"):
                continue
            full = os.path.join(root, path)
            try:
                stat = os.stat(full)
                entries.append(f"{path}:{int(stat.st_mtime_ns)}:{stat.st_size}")
            except OSError:
                entries.append(f"{path}:missing")
    else:
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [
                name
                for name in dirnames
                if name not in {".git", ".atlas_builder", "__pycache__", "node_modules", ".venv"}
            ]
            for name in filenames:
                if not name.endswith(".py"):
                    continue
                rel = os.path.relpath(os.path.join(dirpath, name), root).replace("\\", "/")
                full = os.path.join(root, rel)
                try:
                    stat = os.stat(full)
                    entries.append(f"{rel}:{int(stat.st_mtime_ns)}:{stat.st_size}")
                except OSError:
                    entries.append(f"{rel}:missing")
    entries.sort()
    digest = hashlib.sha256("\n".join(entries).encode("utf-8")).hexdigest()
    return digest[:20]


def engine_versions_blob(packet_format: str) -> Dict[str, Any]:
    from .. import architectural_risk
    from ..bug_intelligence import contract_facts, depgraph, verification_evidence

    return {
        "cache_version": CACHE_VERSION,
        "framework_version": FRAMEWORK_VERSION,
        "schema_version": SCHEMA_VERSION,
        "compact_instrumentation": COMPACT_INSTRUMENTATION_VERSION,
        "architectural_risk_engine": architectural_risk.ENGINE_VERSION,
        "architectural_risk_schema": architectural_risk.SCHEMA_VERSION,
        "depgraph_schema": depgraph.GRAPH_SCHEMA_VERSION,
        "graph_scope": GRAPH_SCOPE,
        "packet_format": packet_format,
        "contract_facts_enabled": contract_facts.CONTRACT_FACTS_ENABLED,
        "verification_evidence_enabled": verification_evidence.VERIFICATION_EVIDENCE_ENABLED,
    }


def versions_digest(packet_format: str) -> str:
    blob = json.dumps(engine_versions_blob(packet_format), sort_keys=True, ensure_ascii=True)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]


def cache_key(
    stage: str,
    repo_path: str,
    fingerprint: str,
    packet_format: str,
) -> str:
    repo_id = hashlib.sha256(os.path.abspath(repo_path).encode("utf-8")).hexdigest()[:12]
    versions = versions_digest(packet_format)
    return f"{repo_id}_{stage}_{GRAPH_SCOPE}_{packet_format}_{versions}_{fingerprint}.json"


def _cache_path(repo_path: str, key: str) -> str:
    return os.path.join(_cache_root(repo_path), key)


class BenchmarkContextSession:
    """Per-repo in-memory session with optional disk cache for expensive stages."""

    def __init__(
        self,
        repo_path: str,
        index: Dict[str, Any],
        *,
        packet_format: Optional[str] = None,
        enabled: Optional[bool] = None,
    ) -> None:
        self.repo_path = os.path.abspath(repo_path)
        self.index = index
        self.packet_format = (packet_format or packet_format_from_env()).lower()
        self.enabled = cache_enabled_from_env() if enabled is None else enabled
        self._fingerprint: Optional[str] = None
        self._memory: Dict[str, Any] = {}
        self._stage_stats: Dict[str, Dict[str, Any]] = {
            stage: {"hits": 0, "misses": 0, "last_hit": False, "last_elapsed_ms": 0.0}
            for stage in CACHED_STAGES
        }

    def fingerprint(self) -> str:
        if self._fingerprint is None:
            self._fingerprint = compute_repo_fingerprint(self.repo_path, self.index)
        return self._fingerprint

    def _record(self, stage: str, *, hit: bool, elapsed_ms: float) -> None:
        stats = self._stage_stats[stage]
        if hit:
            stats["hits"] += 1
        else:
            stats["misses"] += 1
        stats["last_hit"] = hit
        stats["last_elapsed_ms"] = round(elapsed_ms, 3)

    def _load_disk(self, stage: str) -> Optional[Any]:
        if not self.enabled:
            return None
        key = cache_key(stage, self.repo_path, self.fingerprint(), self.packet_format)
        path = _cache_path(self.repo_path, key)
        if not os.path.isfile(path):
            return None
        try:
            return load_json(path)
        except (OSError, json.JSONDecodeError):
            return None

    def _save_disk(self, stage: str, payload: Any) -> None:
        if not self.enabled:
            return
        root = _cache_root(self.repo_path)
        os.makedirs(root, exist_ok=True)
        key = cache_key(stage, self.repo_path, self.fingerprint(), self.packet_format)
        path = _cache_path(self.repo_path, key)
        dump_json(payload, path)

    def _cached(
        self,
        stage: str,
        memory_key: str,
        producer: Any,
    ) -> Any:
        start = time.perf_counter()
        if self.enabled:
            if memory_key in self._memory:
                self._record(stage, hit=True, elapsed_ms=_elapsed_ms(start))
                return self._memory[memory_key]
            disk_payload = self._load_disk(stage)
            if disk_payload is not None:
                self._memory[memory_key] = disk_payload
                self._record(stage, hit=True, elapsed_ms=_elapsed_ms(start))
                return disk_payload
        payload = producer()
        elapsed = _elapsed_ms(start)
        if self.enabled:
            self._memory[memory_key] = payload
            self._save_disk(stage, payload)
            self._record(stage, hit=False, elapsed_ms=elapsed)
        else:
            self._record(stage, hit=False, elapsed_ms=elapsed)
        return payload

    def get_production_subsystems(self) -> List[Dict[str, Any]]:
        def produce() -> List[Dict[str, Any]]:
            from .. import repository_understanding as ru

            from .compact_packets import _is_product_subsystem

            return [
                item
                for item in ru.production_subsystems(self.index)
                if _is_product_subsystem(item)
            ]

        return self._cached("repository_understanding", "subsystems", produce)

    def get_dependency_graph(self) -> Dict[str, Any]:
        def produce() -> Dict[str, Any]:
            from ..bug_intelligence import depgraph

            return depgraph.build_graph(self.repo_path)

        return self._cached("dependency_graph", "graph", produce)

    def get_architectural_risk_ranking(self, *, top: int = 12) -> Dict[str, Any]:
        memory_key = f"architectural_risk_ranking_top_{top}"

        def produce() -> Dict[str, Any]:
            from .. import architectural_risk

            graph = self.get_dependency_graph()
            return architectural_risk.rank_modules(self.index, graph, top=top)

        return self._cached("architectural_risk", memory_key, produce)

    def get_contract_facts_text(self) -> str:
        def produce() -> str:
            from .context_profiling import _probe_contract_facts

            return _probe_contract_facts(self.index)

        return self._cached("contract_facts", "contract_facts_text", produce)

    def get_verification_evidence_text(self) -> str:
        def produce() -> str:
            from .context_profiling import _probe_verification_evidence

            return _probe_verification_evidence(self.index)

        return self._cached("verification_evidence", "verification_text", produce)

    def diagnostics_dict(self) -> Dict[str, Any]:
        return {
            "cache_version": CACHE_VERSION,
            "enabled": self.enabled,
            "repo_path": self.repo_path,
            "packet_format": self.packet_format,
            "repo_fingerprint": self.fingerprint(),
            "graph_scope": GRAPH_SCOPE,
            "engine_versions": engine_versions_blob(self.packet_format),
            "stages": {
                stage: dict(stats) for stage, stats in self._stage_stats.items()
            },
        }


def _elapsed_ms(start: float) -> float:
    return (time.perf_counter() - start) * 1000.0


def get_or_create_session(
    repo_path: str,
    index: Dict[str, Any],
    *,
    packet_format: Optional[str] = None,
) -> BenchmarkContextSession:
    return BenchmarkContextSession(repo_path, index, packet_format=packet_format)


def write_context_profile(
    task_root: str,
    task_id: str,
    session: Optional[BenchmarkContextSession],
    *,
    extra: Optional[Dict[str, Any]] = None,
) -> str:
    payload: Dict[str, Any] = {
        "profiling_version": CACHE_VERSION,
        "task_id": task_id,
        "cache": session.diagnostics_dict() if session else {"enabled": False},
    }
    if extra:
        payload.update(extra)
    out_path = os.path.join(task_root, "context_profile.json")
    dump_json(payload, out_path)
    return out_path
