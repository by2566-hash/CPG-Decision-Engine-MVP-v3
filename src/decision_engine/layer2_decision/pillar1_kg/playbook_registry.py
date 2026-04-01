# ── Layer 2 · Pillar 1 — Playbook Registry ────────────────────────────────
# Loads and manages KG Playbook YAMLs (platform-level, stable weeks/months).
# Contains: trigger conditions, pattern→cause→action mappings, constraints.
# Domain expert (partner) manages YAML content. Architecture manages this file.
#
# Callchain in pipeline._generate_candidates():
#   1. match_playbook(module, pattern) → find matching playbook
#   2. get_base_utility(playbook_id, context) → U_base from playbook
#   3. If None → fallback to ImpactCalculator.INDUSTRY_BENCHMARKS
#
# YAML schema (expected fields from partner):
#   playbook.id:       str   — unique identifier
#   playbook.module:   str   — retention | acquisition | conversion | promotion
#   actions[].id:      str   — action_id e.g. DISCOUNT_10PCT
#   actions[].expected_utility: float  — U_base(KG) prior (partner fills this in)
#   triggers[].condition: str  — trigger expression
#   triggers[].msm_state:  str  — WATCH | DEGRADING | CRITICAL
#
# V3: 4 modules (retention + 3 new: acquisition, conversion, promotion)
# Reference: V0/playbook_engine/ (retention playbook — extended to 4 modules)
# ───────────────────────────────────────────────────────────────────────────
from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

# Default playbook directory relative to project root
_DEFAULT_PLAYBOOK_DIR = str(
    Path(__file__).resolve().parents[5] / "playbooks"
)


class PlaybookRegistry:
    """Loads, validates, and serves KG Playbook YAMLs.

    Partner fills in YAML content (expected_utility, trigger conditions, patterns).
    This class manages the loading, indexing, and lookup — independent of YAML content.
    """

    def __init__(self, playbook_dir: str | None = None) -> None:
        self._playbook_dir = playbook_dir or _DEFAULT_PLAYBOOK_DIR
        # Index: module → list of playbooks (ordered by specificity)
        self._by_module: dict[str, list[dict[str, Any]]] = {}
        # Index: playbook_id → playbook
        self._by_id: dict[str, dict[str, Any]] = {}
        self._loaded = False

    def _ensure_loaded(self) -> None:
        """Lazy load — called on first use to avoid import-time filesystem access."""
        if not self._loaded:
            self.load_playbooks(self._playbook_dir)

    def load_playbooks(self, playbook_dir: str) -> None:
        """Load all playbook YAML files from directory. Index by module and id.

        Silently skips files that cannot be parsed (partner may deliver incrementally).
        Requires pyyaml (already in project dependencies).
        """
        import yaml  # lazy import — only needed here

        self._by_module.clear()
        self._by_id.clear()

        pb_path = Path(playbook_dir)
        if not pb_path.exists():
            log.warning("[playbook_registry] Playbook dir not found: %s", playbook_dir)
            self._loaded = True
            return

        yaml_files = list(pb_path.glob("*.yaml")) + list(pb_path.glob("*.yml"))
        loaded = 0
        for fpath in sorted(yaml_files):
            try:
                with open(fpath, "r", encoding="utf-8") as fh:
                    data = yaml.safe_load(fh)

                if not isinstance(data, dict) or "playbook" not in data:
                    log.debug("[playbook_registry] Skipping %s: missing 'playbook' key", fpath.name)
                    continue

                pb_meta = data["playbook"]
                pb_id = pb_meta.get("id", fpath.stem)
                module = pb_meta.get("module", "")

                # Merge top-level keys into a flat playbook dict for easy access
                playbook: dict[str, Any] = {
                    "id": pb_id,
                    "module": module,
                    "description": pb_meta.get("description", ""),
                    "actions": data.get("actions", []),
                    "triggers": data.get("triggers", []),
                    "patterns": data.get("patterns", []),
                    "constraints": data.get("constraints", []),
                    "_source_file": fpath.name,
                }

                self._by_id[pb_id] = playbook
                self._by_module.setdefault(module, []).append(playbook)
                loaded += 1

            except Exception:
                log.warning("[playbook_registry] Failed to load %s", fpath.name, exc_info=True)

        log.info("[playbook_registry] Loaded %d playbooks from %s", loaded, playbook_dir)
        self._loaded = True

    def match_playbook(self, module: str, pattern: dict) -> dict | None:
        """Find best matching playbook for a module + MSM state context.

        Phase 1: return the first playbook for the module (simple module match).
        Phase 2: evaluate trigger conditions in pattern against playbook triggers.

        Returns None if no playbook registered for this module.
        Partner fills in trigger conditions; architecture wires the lookup.
        """
        self._ensure_loaded()

        candidates = self._by_module.get(module)
        if not candidates:
            return None

        # Phase 2: evaluate trigger conditions (msm_state match)
        # For now, return the best match based on msm_state alignment
        msm_state = pattern.get("msm_state", "")
        for pb in candidates:
            for trigger in pb.get("triggers", []):
                if trigger.get("msm_state", "") == msm_state:
                    return pb

        # Fallback: return the first playbook for the module
        return candidates[0]

    def get_base_utility(self, playbook_id: str, context: dict) -> float | None:
        """Get U_base(KG) from playbook action definition.

        Returns the partner-defined expected_utility for the given action_id.
        Returns None if:
          - playbook not found
          - action not in playbook
          - action has no expected_utility (partner hasn't filled it in yet)

        When None is returned, pipeline falls back to INDUSTRY_BENCHMARKS.
        Partner fills in expected_utility values in the YAML files.
        """
        self._ensure_loaded()

        playbook = self._by_id.get(playbook_id)
        if not playbook:
            return None

        action_id = context.get("action_id", "")
        for action in playbook.get("actions", []):
            if action.get("id") == action_id:
                utility = action.get("expected_utility")
                if utility is not None:
                    return float(utility)
                break  # Action found but no expected_utility yet

        return None  # Not defined — partner fills this in

    def list_modules(self) -> list[str]:
        """Return all modules with registered playbooks."""
        self._ensure_loaded()
        return list(self._by_module.keys())

    def get_playbook(self, playbook_id: str) -> dict | None:
        """Return a playbook by id."""
        self._ensure_loaded()
        return self._by_id.get(playbook_id)
