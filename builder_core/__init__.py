"""builder_core: standalone Builder Core CLI MVP.

A local-only, read-only project intelligence layer that works on *any*
repository (not just the Atlas repo). It indexes a project, answers
questions with extractive evidence, and stores builder decisions.

Hard boundaries (by design):
- Touches no voice / browser / trading / website code.
- Does not modify Phase 79 or any existing module.
- The only writes it performs are project-memory/index files under
  ``<project>/.atlas_builder/``.
- No network, no LLM required.
"""

__version__ = "0.1.0"

MEMORY_DIRNAME = ".atlas_builder"
INDEX_FILENAME = "index.json"
DECISIONS_FILENAME = "decisions.jsonl"
