"""Feature Plane — continuous numeric features for scoring and learning.

Implements ADR-0005: Feature Plane as logical concept.

Computes DecisionFeatureVector instances from raw signals, providing a
stable typed contract for downstream scoring and future bandit training.
No storage or online/offline split in Phase 1.

See V3/docs/adr/0005-feature-plane-as-logical-concept-no-infrastructure-phase-1.md
See V3/docs/PHASE_ROADMAP.md Phase 1 / Feature Plane implementation
"""

from .builder import FeatureBuilder

__all__ = ["FeatureBuilder"]
