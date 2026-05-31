"""Compatibility facade for the Phase 95A validation harness.

The real implementation lives outside the detector package so the measurement
layer stays visibly separate from Builder Core intelligence.
"""

from builder_core.real_repo_validation.harness import *  # noqa: F401,F403
