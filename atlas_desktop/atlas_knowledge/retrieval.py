"""Knowledge retrieval policy — local first, web only as fallback (Phase 127).

No network calls are made in this module by default. Web retrieval is a stub for
future integration behind explicit configuration.
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from .schema import ConceptRecord, validate_concept

# Concepts that must NEVER trigger web retrieval (stable engineering knowledge).
RETRIEVAL_BLOCKLIST: Set[str] = {
    "ema", "rsi", "macd", "jwt", "oauth", "oauth2", "postgresql", "postgres",
    "react", "rate_limiting", "retry", "queue", "redis", "kubernetes", "docker",
    "grpc", "rest", "graphql", "stripe_billing", "authentication", "authorization",
    "cors", "csrf", "sql_injection", "xss", "https", "tls", "load_balancer",
    "circuit_breaker", "idempotency", "event_sourcing", "cqrs", "microservices",
    "monolith", "caching", "index_btree", "database_migration", "ci_cd",
}

# Freshness-sensitive prefixes (retrieval allowed when local miss).
FRESHNESS_PREFIXES = (
    "openai_api",
    "anthropic_api",
    "kubernetes_1_",
    "stripe_api_version",
)


class RetrievalPolicy:
  """Local → cached → trusted retrieval (stub)."""

  def __init__(self, cache_dir: Path, *, enabled: bool = False) -> None:
      self.cache_dir = cache_dir
      self.enabled = enabled  # web retrieval off by default
      self.cache_dir.mkdir(parents=True, exist_ok=True)

  def should_retrieve(
      self,
      text: str,
      *,
      local_score: float,
      matched_id: Optional[str],
      threshold: float,
  ) -> bool:
      if matched_id and matched_id.lower() in RETRIEVAL_BLOCKLIST:
          return False
      if local_score >= threshold:
          return False
      norm = re.sub(r"\s+", " ", (text or "").lower())
      for blocked in RETRIEVAL_BLOCKLIST:
          if blocked in norm:
              return False
      if not self.enabled:
          return False
      # Only allow retrieval for freshness-sensitive queries
      return any(p in norm for p in ("latest", "new version", "api version", "sdk"))

  def load_cached(self, concept_id: str) -> Optional[ConceptRecord]:
      path = self.cache_dir / f"{concept_id}.json"
      if not path.is_file():
          return None
      try:
          raw = json.loads(path.read_text(encoding="utf-8"))
          rec = ConceptRecord.from_dict(raw)
          ok, _ = validate_concept(rec, strict=False)
          return rec if ok else None
      except (OSError, ValueError, json.JSONDecodeError):
          return None

  def save_cached(self, record: ConceptRecord, *, source: str = "retrieval_stub") -> None:
      path = self.cache_dir / f"{record.concept_id}.json"
      payload = record.to_dict()
      payload["_cached_at"] = time.time()
      payload["_source"] = source
      path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

  def create_temporary_concept(self, text: str, domain: str = "general") -> ConceptRecord:
      """Low-confidence placeholder when no local match (not persisted unless cached)."""
      slug = re.sub(r"[^a-z0-9]+", "_", text.lower())[:48].strip("_") or "unknown"
      cid = f"temp_{slug}_{int(time.time()) % 100000}"
      return ConceptRecord(
          concept_id=cid,
          name=text[:80],
          aliases=[text.lower()[:120]],
          domain=domain,
          category="unknown",
          description=f"Temporary concept created from user text (not in catalog): {text[:200]}",
          requirements=["Clarify scope and gather authoritative references before implementing."],
          common_implementations=[],
          risks=["Unvalidated temporary concept — verify with official documentation."],
          failure_modes=["Misapplied pattern due to incomplete local knowledge."],
          verification=["Confirm requirements with team and official docs."],
          testing=["Add tests once design is validated."],
          related_concepts=[],
          references=[],
          confidence="low",
          path_keywords=[],
      )

  def attempt_retrieval(self, text: str, domain: str = "general") -> Optional[ConceptRecord]:
      """Stub: no HTTP. Returns temporary concept for cache reuse."""
      if not self.enabled:
          return None
      rec = self.create_temporary_concept(text, domain)
      self.save_cached(rec, source="retrieval_stub")
      return rec
