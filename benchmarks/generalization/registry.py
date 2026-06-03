"""Phase 136 — target repository registry for the generalization benchmark.

Paths are resolved from (in priority order):
  1. an explicit env var ``ATLAS_BENCH_<NAME>`` (upper-cased repo id),
  2. a small set of conventional local locations,
  3. otherwise the repo is marked unavailable (the framework still emits a row
     so the suite stays reproducible once the checkout exists).

NOTHING here clones or downloads — measurement only.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

# Conventional roots to probe for a checkout named like the repo id.
_SEARCH_ROOTS = [
    Path(r"C:\J.A.R.V.I.S"),
    Path(r"C:\J.A.R.V.I.S\local_jarvis\external_repos"),
    Path(r"C:\repos"),
    Path(r"C:\src"),
    Path(os.path.expanduser("~")) / "source" / "repos",
    Path(__file__).resolve().parents[2] / "external_repos",
]


@dataclass
class RepoSpec:
    id: str
    display: str
    language: str
    framework: str
    category: str  # python | typescript | infrastructure
    aliases: List[str] = field(default_factory=list)
    # Concept tokens this repo is expected to expose (for impact prompts). Generic
    # prompts run on every repo; these add repo-relevant variants.
    impact_concepts: List[str] = field(default_factory=list)

    def resolve_path(self) -> Optional[Path]:
        env = os.environ.get(f"ATLAS_BENCH_{self.id.upper()}")
        if env and Path(env).is_dir():
            return Path(env)
        names = [self.id] + self.aliases
        for root in _SEARCH_ROOTS:
            for name in names:
                cand = root / name
                if cand.is_dir():
                    return cand
        return None


# 11 target repositories across languages / frameworks / layouts.
REPOS: List[RepoSpec] = [
    RepoSpec("home_assistant", "Home Assistant", "python", "asyncio platform", "python",
             aliases=["homeassistant", "core"],
             impact_concepts=["websocket support", "the event bus", "config entries", "the recorder"]),
    RepoSpec("django", "Django", "python", "web framework", "python",
             impact_concepts=["the ORM", "middleware", "the template engine", "the auth backend"]),
    RepoSpec("fastapi", "FastAPI", "python", "web framework", "python",
             impact_concepts=["dependency injection", "routing", "request validation"]),
    RepoSpec("langchain", "LangChain", "python", "LLM framework", "python",
             aliases=["langchain", "langchain-master"],
             impact_concepts=["the agent executor", "memory", "the retriever", "chains"]),
    RepoSpec("openbb", "OpenBB", "python", "fintech platform", "python",
             aliases=["OpenBB", "OpenBBTerminal"],
             impact_concepts=["the data provider", "the router", "extensions"]),
    RepoSpec("vscode", "VS Code", "typescript", "Electron IDE", "typescript",
             aliases=["vscode", "VSCode"],
             impact_concepts=["the extension host", "the editor", "the command registry", "workbench"]),
    RepoSpec("nextjs", "Next.js", "typescript", "React framework", "typescript",
             aliases=["next.js", "next"],
             impact_concepts=["routing", "the compiler", "server components"]),
    RepoSpec("react", "React", "typescript", "UI library", "typescript",
             impact_concepts=["the reconciler", "the scheduler", "hooks"]),
    RepoSpec("nestjs", "NestJS", "typescript", "Node framework", "typescript",
             aliases=["nest"],
             impact_concepts=["the dependency injector", "middleware", "guards", "the router"]),
    RepoSpec("kubernetes", "Kubernetes (kubelet)", "go", "container orchestrator", "infrastructure",
             aliases=["kubernetes", "k8s"],
             impact_concepts=["the scheduler", "the api server", "the controller manager"]),
    RepoSpec("qdrant", "Qdrant", "rust", "vector database", "infrastructure",
             impact_concepts=["the storage engine", "the collection manager", "search"]),
    # Extra real repositories available locally (broaden layout coverage beyond the
    # 11 marquee targets — different package structures, sizes and conventions).
    RepoSpec("atlas_self", "Atlas (local_jarvis)", "python", "desktop tool", "python",
             aliases=["local_jarvis"],
             impact_concepts=["the impact engine", "the planning engine", "the architecture analyzer"]),
    RepoSpec("quixbugs", "QuixBugs", "python", "algorithms corpus", "python",
             aliases=["QuixBugs"],
             impact_concepts=["the graph algorithms", "node"]),
]


def available_repos() -> List["ResolvedRepo"]:
    out: List[ResolvedRepo] = []
    for spec in REPOS:
        out.append(ResolvedRepo(spec=spec, path=spec.resolve_path()))
    return out


@dataclass
class ResolvedRepo:
    spec: RepoSpec
    path: Optional[Path]

    @property
    def available(self) -> bool:
        return self.path is not None
