# ── Layer 2 · Pillar 1 — Playbook Registry ────────────────────────────────
# Loads and manages KG Playbook YAMLs (platform-level, stable weeks/months).
# Contains: trigger conditions, pattern→cause→action mappings, constraints.
# Domain expert (partner) manages YAML content. Architecture manages this file.
#
# Three-layer KG structure [ADR-0011]:
#   Layer 1: playbooks/meta/*.yaml          — meta-patterns (platform-level)
#   Layer 2: playbooks/brands/{id}/*.yaml   — brand bindings (per-brand)
#   Layer 3: PolicyPack.alert_thresholds    — dynamic, calibration-updated
#
# Callchain in pipeline._generate_candidates():
#   1. match_playbook(module, pattern) → find matching playbook
#   2. get_base_utility(playbook_id, context) → U_base, priority order:
#      a. Brand binding gmv_lift_prior (if merchant_id in context)
#      b. Flat playbook expected_utility (legacy path)
#      c. None → fallback to ImpactCalculator.INDUSTRY_BENCHMARKS
#
# gmv_lift_prior is always clipped to [0.0, _GMV_LIFT_MAX] to prevent
# bandit exploration weight explosion on small merchants with high AOV.
#
# YAML schema (flat playbook, expected fields from partner):
#   playbook.id:       str   — unique identifier
#   playbook.module:   str   — retention | acquisition | conversion | promotion
#   actions[].id:      str   — action_id e.g. DISCOUNT_10PCT
#   actions[].expected_utility: float  — U_base(KG) prior (partner fills this in)
#   triggers[].condition: str  — trigger expression
#   triggers[].msm_state:  str  — WATCH | DEGRADING | CRITICAL
#
# Brand binding YAML schema (playbooks/brands/{merchant_id}/*.yaml):
#   brand:                str   — merchant slug
#   meta_pattern_ref:     str   — references a meta-pattern or flat playbook id
#   thresholds:           dict  — per-brand threshold values + calibration_status
#   action_utility_priors: dict — per-action gmv_lift_prior + evidence_case pointer
#
# V3: 4 modules (retention + 3 new: acquisition, conversion, promotion)
# Reference: ADR-0011, docs/playbook_authoring_sop.md
# ───────────────────────────────────────────────────────────────────────────
from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

from ...utils.path_utils import safe_merchant_id

log = logging.getLogger(__name__)

# Hard clip for gmv_lift_prior: scoring.py clips at _clip(pred / 0.30),
# so the effective ceiling is 0.30. We clip at 0.25 at input to leave
# headroom and prevent bandit weight explosion on small/high-AOV merchants.
_GMV_LIFT_MAX = 0.25

# Default playbook directory relative to V3 project root.
# Path depth from this file to V3/:
#   playbook_registry.py → pillar1_kg/ → layer2_decision/ → decision_engine/ → src/ → V3/
# That is 5 path components up = parents[4].
_DEFAULT_PLAYBOOK_DIR = str(
    Path(__file__).resolve().parents[4] / "playbooks"
)


def _render_template(raw: str, flat: dict[str, str]) -> str:
    """Replace ${key.subkey} patterns using a pre-flattened dot-notation dict.

    Supports dots in key names (e.g. ${thresholds.cac_spike_ratio}), which
    string.Template cannot handle. Undefined variables are left as-is.
    """
    def replacer(match: re.Match) -> str:
        key = match.group(1)
        return flat.get(key, match.group(0))  # leave undefined as-is

    return re.sub(r"\$\{([^}]+)\}", replacer, raw)


def _flatten_dict(d: dict, prefix: str = "") -> dict[str, str]:
    """Flatten nested dict into dot-notation keys for string.Template substitution.

    {"thresholds": {"cac_spike_ratio": 1.15}} →
    {"thresholds.cac_spike_ratio": "1.15"}

    All values are converted to str so Template.safe_substitute() works correctly.
    """
    result: dict[str, str] = {}
    for k, v in d.items():
        key = f"{prefix}.{k}" if prefix else k
        if isinstance(v, dict):
            result.update(_flatten_dict(v, key))
        else:
            result[key] = str(v)
    return result


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
        # Brand binding cache: merchant_id → {meta_pattern_ref → binding_dict}
        # Loaded lazily on first get_base_utility() call with a merchant_id.
        self._brand_bindings: dict[str, dict[str, dict[str, Any]]] = {}

    def _ensure_loaded(self) -> None:
        """Lazy load — called on first use to avoid import-time filesystem access."""
        if not self._loaded:
            self.load_playbooks(self._playbook_dir)

    def load_playbooks(self, playbook_dir: str) -> None:
        """Load all playbook YAML files from directory. Index by module and id.

        Skips files that cannot be parsed (partner may deliver incrementally).
        Calls _validate_playbook_structure() on each loaded playbook and emits
        WARNING logs for every structural issue found — partner must fix warnings
        before this playbook will generate correct candidates.
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

        # Scan root (flat stub playbooks) + meta/ (ADR-0011 Layer 1 meta-patterns).
        # meta/ files use the 'meta_pattern:' top-level key instead of 'playbook:'.
        # Subdirectories starting with '_' (e.g. _deferred/) are skipped — they
        # contain dormant patterns awaiting Phase 2 dependencies. Loading them
        # would register non-activatable triggers as live candidates.
        meta_path = pb_path / "meta"
        meta_yamls = [
            f for f in (
                list(meta_path.glob("*.yaml")) + list(meta_path.glob("*.yml"))
            )
            if not any(part.startswith("_") for part in f.relative_to(pb_path).parts)
        ] if meta_path.exists() else []
        yaml_files = (
            list(pb_path.glob("*.yaml")) + list(pb_path.glob("*.yml"))
            + meta_yamls
        )
        loaded = 0
        for fpath in sorted(yaml_files):
            try:
                with open(fpath, "r", encoding="utf-8") as fh:
                    data = yaml.safe_load(fh)

                if not isinstance(data, dict):
                    log.warning(
                        "[playbook_registry] Skipping %s: not a valid YAML dict.",
                        fpath.name,
                    )
                    continue

                # Support both flat playbooks ('playbook:' key) and ADR-0011 meta-patterns
                # ('meta_pattern:' key). Normalize to a single internal structure.
                is_meta = "meta_pattern" in data
                if is_meta:
                    pb_meta = data["meta_pattern"]
                elif "playbook" in data:
                    pb_meta = data["playbook"]
                else:
                    log.warning(
                        "[playbook_registry] Skipping %s: missing 'playbook' or 'meta_pattern' key. "
                        "Check YAML schema — this file produces zero candidates.",
                        fpath.name,
                    )
                    continue

                pb_id = pb_meta.get("id", fpath.stem)
                module = pb_meta.get("module", "")

                # Merge top-level keys into a flat playbook dict for easy access.
                # _is_meta=True marks ADR-0011 Layer 1 meta-patterns; these are
                # preferred over flat stub playbooks in match_playbook().
                playbook: dict[str, Any] = {
                    "id": pb_id,
                    "module": module,
                    "description": pb_meta.get("description", ""),
                    "actions": data.get("actions", []),
                    "triggers": data.get("triggers", []),
                    "patterns": data.get("patterns", []),
                    "constraints": data.get("constraints", []),
                    "_source_file": fpath.name,
                    "_is_meta": is_meta,  # True = ADR-0011 meta-pattern; False = flat stub
                }

                # Validate structure — issues are logged but never block loading.
                # A playbook with issues is still indexed; partner must fix warnings.
                issues = self._validate_playbook_structure(playbook)
                for issue in issues:
                    log.warning("[playbook_registry] %s: %s", fpath.name, issue)

                self._by_id[pb_id] = playbook
                self._by_module.setdefault(module, []).append(playbook)
                loaded += 1

            except Exception:
                log.warning("[playbook_registry] Failed to load %s", fpath.name, exc_info=True)

        log.info("[playbook_registry] Loaded %d playbooks from %s", loaded, playbook_dir)
        self._loaded = True

    # ── Playbook structure validation ────────────────────────────────────────

    _VALID_MODULES = frozenset({"retention", "acquisition", "conversion", "promotion"})
    _VALID_MSM_STATES = frozenset({"HEALTHY", "WATCH", "DEGRADING", "CRITICAL"})

    # Governed threshold key namespace [ADR-0011 / SOP Section 5].
    # Add new ACTIVE keys here AND in docs/playbook_authoring_sop.md Section 5 table
    # with status=active and introduced_at annotation.
    # Unknown keys at brand binding load time emit a WARNING (not an error).
    _KNOWN_THRESHOLD_KEYS = frozenset({
        "cac_spike_ratio",
        "cac_critical_ratio",
        "sub_rate_alert_pct",
        "sub_rate_critical_pct",
        "sku_concentration_threshold",
        "channel_nonsubscribable_share",
        "destination_cpp_gap_threshold",  # renamed from destination_cvr_gap_threshold 2026-04-16: CPP replaces CVR per partner calibration
        "mix_diagnosis_min_delta_pp",
        # ── cba_001 (acquisition_ugc_creative) ──────────────────────────────
        "cpm_spike_ratio",           # CPM above baseline × multiplier → WATCH
        "creative_ugc_share_floor",  # min UGC share of spend to consider creative mix healthy
        # ── cba_002 (conversion_compliance_friction) ─────────────────────────
        "cvr_collapse_threshold",    # CVR drop fraction (vs baseline) that triggers CRITICAL
        "recent_change_window_days", # days look-back for site/flow/legal change detection
    })

    # Threshold metadata fields: present alongside thresholds but are not
    # signal threshold variables. Skipped during unknown-key validation.
    _THRESHOLD_METADATA_FIELDS = frozenset({
        "calibration_status",
    })

    # Dormant threshold keys: pre-registered for Phase 2 patterns in _deferred/.
    # Keys here are KNOWN (no "unknown key" warning) but BLOCKED — any active
    # brand binding that references a dormant key emits a distinctive WARNING.
    # [SOP Section 5 / ADR-0012]
    _DORMANT_THRESHOLD_KEYS = frozenset({
        # ── cbb_001 (acquisition_ltv_quality_trap, Phase 2) ─────────────────
        "cac_improvement_floor",           # retargeting CAC floor below which LTV trap suspected
        "offer_creative_share_threshold",  # offer-led creative share of retargeting spend
        # ── demoted 2026-04-16: registered but unexercised, no active pattern reference ──
        "brand_dr_split_threshold",        # brand spend fraction → require separate CPA view
        "inventory_safety_days",           # inventory days threshold for spend reduction
    })

    # Valid calibration_status values [ADR-0011]
    _VALID_CALIBRATION_STATUSES = frozenset({"partner_prior", "outcome_calibrated"})

    def _validate_playbook_structure(self, playbook: dict) -> list[str]:
        """Check a loaded playbook dict for structural issues.

        Returns a list of human-readable problem strings (empty list = all good).
        Never raises — caller logs and continues.

        Checks:
          1. module is one of the 4 known CPG modules
          2. actions list is non-empty
          3. each action has 'id' and numeric 'expected_utility'
          4. triggers list is non-empty
          5. each trigger has a valid 'msm_state'
        """
        issues: list[str] = []
        pb_id = playbook.get("id", "<unknown>")

        # 1. module must be a known CPG module — wrong name = zero candidates routed here
        module = playbook.get("module", "")
        if not module:
            issues.append(
                f"[{pb_id}] playbook.module is missing — candidates will never be routed"
            )
        elif module not in self._VALID_MODULES:
            issues.append(
                f"[{pb_id}] playbook.module='{module}' is not a valid CPG module "
                f"(valid: {sorted(self._VALID_MODULES)})"
            )

        # 2. actions must be non-empty — no actions = no candidates
        is_meta = playbook.get("_is_meta", False)
        actions = playbook.get("actions", [])
        if not actions:
            issues.append(f"[{pb_id}] actions list is empty — no candidates will be generated")
        else:
            for i, action in enumerate(actions):
                aid = action.get("id", f"actions[{i}]")
                # 3a. action must have an id
                if not action.get("id"):
                    issues.append(f"[{pb_id}] actions[{i}] missing 'id' field")
                # 3b. expected_utility check.
                # ADR-0011 meta-patterns: U_base comes from brand bindings, not inline
                # expected_utility — skip the numeric check for meta-pattern actions.
                # Flat stub playbooks: expected_utility is required.
                utility = action.get("expected_utility")
                if not is_meta:
                    if utility is None:
                        issues.append(
                            f"[{pb_id}] action '{aid}' missing 'expected_utility' — "
                            f"scoring will fall back to INDUSTRY_BENCHMARKS (lower confidence)"
                        )
                    elif not isinstance(utility, (int, float)):
                        issues.append(
                            f"[{pb_id}] action '{aid}' expected_utility={utility!r} is not numeric"
                        )

        # 4. triggers must be non-empty — no triggers = only last-resort fallback match
        triggers = playbook.get("triggers", [])
        if not triggers:
            issues.append(
                f"[{pb_id}] triggers list is empty — "
                f"match_playbook() returns this only as last-resort fallback"
            )
        else:
            for i, trigger in enumerate(triggers):
                msm_state = trigger.get("msm_state", "")
                # 5. each trigger must have a valid msm_state
                if not msm_state:
                    issues.append(
                        f"[{pb_id}] triggers[{i}] missing 'msm_state' field — "
                        f"this trigger will never match"
                    )
                elif msm_state not in self._VALID_MSM_STATES:
                    issues.append(
                        f"[{pb_id}] triggers[{i}] msm_state='{msm_state}' is not valid "
                        f"(valid: {sorted(self._VALID_MSM_STATES)})"
                    )

        return issues

    def _validate_brand_binding(self, data: dict, filename: str) -> None:
        """Warn on governance violations in a brand binding dict.

        Checks:
          1. Unknown threshold keys (not in _KNOWN_THRESHOLD_KEYS)
          2. Invalid calibration_status values
        Never raises — only emits warnings so loading always succeeds.
        """
        brand = data.get("brand", filename)
        thresholds = data.get("thresholds", {})

        # 1. Threshold key governance: check for dormant keys first (more specific
        #    warning), then unknown keys. Dormant keys are pre-registered for
        #    Phase 2 patterns and must NOT appear in active brand bindings.
        #    Metadata fields (_THRESHOLD_METADATA_FIELDS) are skipped entirely.
        for key in thresholds:
            if key in self._THRESHOLD_METADATA_FIELDS:
                continue
            if key in self._DORMANT_THRESHOLD_KEYS:
                log.warning(
                    "[playbook_registry] %s: threshold key '%s' is DORMANT — "
                    "it belongs to a Phase 2 deferred pattern (playbooks/meta/_deferred/) "
                    "and must not be referenced in an active brand binding. "
                    "See docs/partner_clarification_queue/ and ADR-0012.",
                    brand, key,
                )
            elif key not in self._KNOWN_THRESHOLD_KEYS:
                log.warning(
                    "[playbook_registry] %s: unknown threshold key '%s' — "
                    "add to _KNOWN_THRESHOLD_KEYS and SOP Section 5 table. "
                    "See docs/playbook_authoring_sop.md.",
                    brand, key,
                )

        # 2. calibration_status value validation
        cal_status = thresholds.get("calibration_status")
        if cal_status is not None and cal_status not in self._VALID_CALIBRATION_STATUSES:
            log.warning(
                "[playbook_registry] %s: thresholds.calibration_status='%s' is not a "
                "valid CalibrationStatus (valid: %s).",
                brand, cal_status, sorted(self._VALID_CALIBRATION_STATUSES),
            )

        # Per-action calibration_status validation
        for action_id, prior in data.get("action_utility_priors", {}).items():
            if isinstance(prior, dict):
                action_cal = prior.get("calibration_status")
                if action_cal is not None and action_cal not in self._VALID_CALIBRATION_STATUSES:
                    log.warning(
                        "[playbook_registry] %s: action_utility_priors.%s.calibration_status='%s' "
                        "is not valid (valid: %s).",
                        brand, action_id, action_cal, sorted(self._VALID_CALIBRATION_STATUSES),
                    )

    def match_playbook(self, module: str, pattern: dict, merchant_id: str = "") -> dict | None:
        """Find best matching playbook for a module + MSM state context.

        ADR-0012 contract: returns dict | None (single playbook, never a list).
        Premise: brand-bound patterns within the same module have mutually
        exclusive trigger conditions. If this premise is violated, escalate to
        list[dict] return type per ADR-0012 supersession process.

        Selection priority (in order):
          1. Brand-bound meta-pattern matching MSM state, alphabetical by id.
             Requires merchant_id. Uses get_brand_binding() — triggers lazy load.
          2. Any meta-pattern matching MSM state (first found, load order).
          3. Any flat playbook matching MSM state (first found).
          4. Any meta-pattern (no MSM state match — last-resort).
          5. First registered playbook for module.

        Args:
          module:      CPG module name (retention | acquisition | conversion | promotion)
          pattern:     context dict; pattern["msm_state"] drives trigger matching
          merchant_id: if provided, enables brand-binding-aware selection (Priority 1)
        """
        self._ensure_loaded()

        candidates = self._by_module.get(module)
        if not candidates:
            return None

        # Collect all MSM-state-matching playbooks by tier.
        # ADR-0011: meta-patterns take priority over flat stubs.
        msm_state = pattern.get("msm_state", "")
        meta_matches: list[dict] = []
        flat_match: dict | None = None

        for pb in candidates:
            for trigger in pb.get("triggers", []):
                if trigger.get("msm_state", "") == msm_state:
                    if pb.get("_is_meta"):
                        meta_matches.append(pb)
                    elif flat_match is None:
                        flat_match = pb
                    break  # one trigger match per playbook is enough

        if meta_matches:
            # Priority 1: brand-bound meta-pattern, deterministic alphabetical by id.
            # Alphabetical order is the tiebreak for mutual-exclusivity; if two patterns
            # are truly exclusive only one will ever bind at runtime. [ADR-0012]
            if merchant_id:
                bound = [pb for pb in meta_matches
                         if self.get_brand_binding(merchant_id, pb["id"])]
                if bound:
                    return min(bound, key=lambda pb: pb["id"])
            # Priority 2: first meta-pattern in load order (no brand binding)
            return meta_matches[0]

        if flat_match:
            return flat_match

        # No MSM state match: prefer any meta-pattern over flat stubs
        for pb in candidates:
            if pb.get("_is_meta"):
                return pb
        return candidates[0]

    def get_base_utility(self, playbook_id: str, context: dict) -> float | None:
        """Get U_base(KG) for a given action. [ADR-0011 priority order]

        Priority 1: Brand binding gmv_lift_prior (if merchant_id in context).
          Loaded lazily from playbooks/brands/{merchant_id}/*.yaml.
          Hard-clipped to [0.0, _GMV_LIFT_MAX=0.25].

        Priority 2: Flat playbook expected_utility (legacy path).
          Also clipped to [0.0, _GMV_LIFT_MAX].

        Priority 3: None — caller falls back to INDUSTRY_BENCHMARKS.

        context keys:
          action_id (str): required — which action to look up
          merchant_id (str): optional — if provided, enables brand binding lookup
        """
        self._ensure_loaded()

        action_id = context.get("action_id", "")
        merchant_id = context.get("merchant_id", "")

        # Priority 1: brand binding gmv_lift_prior
        if merchant_id:
            raw = self._get_brand_binding_utility(merchant_id, playbook_id, action_id)
            if raw is not None:
                return self._clip_utility(raw, playbook_id, action_id)

        # Priority 2: flat playbook expected_utility (legacy)
        playbook = self._by_id.get(playbook_id)
        if not playbook:
            return None

        for action in playbook.get("actions", []):
            if action.get("id") == action_id:
                utility = action.get("expected_utility")
                if utility is not None:
                    return self._clip_utility(float(utility), playbook_id, action_id)
                break  # Action found but no expected_utility yet

        return None  # Not defined — caller falls back to INDUSTRY_BENCHMARKS

    # ── Brand Binding (ADR-0011) ─────────────────────────────────────────────

    def load_brand_binding(self, merchant_id: str) -> dict[str, Any]:
        """Load all brand binding YAMLs for a merchant into the cache.

        Scans playbooks/brands/{merchant_id}/*.yaml.
        Indexes by meta_pattern_ref so get_base_utility() can look up by
        playbook_id (which matches meta_pattern_ref in brand bindings).

        Safe to call multiple times — reloads from disk each time.
        Returns the loaded bindings dict (meta_pattern_ref → binding).
        """
        import yaml  # lazy import

        # Empty merchant_id means "no specific merchant" (test/fallback context).
        # No brand dir to load — return empty gracefully without path validation.
        if not merchant_id:
            self._brand_bindings[merchant_id] = {}
            return {}

        brand_dir = Path(self._playbook_dir) / "brands" / safe_merchant_id(merchant_id)
        if not brand_dir.exists():
            log.debug("[playbook_registry] No brand binding dir for %s", merchant_id)
            self._brand_bindings[merchant_id] = {}
            return {}

        bindings: dict[str, Any] = {}
        for fpath in sorted(brand_dir.glob("*.yaml")):
            try:
                with open(fpath, "r", encoding="utf-8") as fh:
                    data = yaml.safe_load(fh)
                if not isinstance(data, dict):
                    log.warning("[playbook_registry] Brand binding %s is not a dict — skipped", fpath.name)
                    continue
                meta_ref = data.get("meta_pattern_ref", fpath.stem)
                bindings[meta_ref] = data
                self._validate_brand_binding(data, fpath.name)
                log.debug("[playbook_registry] Loaded brand binding %s → %s", fpath.name, meta_ref)
            except Exception:
                log.warning("[playbook_registry] Failed to load brand binding %s", fpath.name, exc_info=True)

        self._brand_bindings[merchant_id] = bindings
        log.info("[playbook_registry] Loaded %d brand bindings for %s", len(bindings), merchant_id)
        return bindings

    def get_brand_binding(self, merchant_id: str, meta_pattern_ref: str) -> dict | None:
        """Return brand binding for merchant × meta_pattern_ref, or None.

        Triggers lazy load if merchant not yet in cache.
        """
        if merchant_id not in self._brand_bindings:
            self.load_brand_binding(merchant_id)
        return self._brand_bindings.get(merchant_id, {}).get(meta_pattern_ref)

    def render_brand_triggers(self, meta_pattern_raw_yaml: str, merchant_id: str, meta_pattern_ref: str) -> dict | None:
        """Interpolate ${thresholds.*} and ${entity_bindings.*} in a meta-pattern YAML.

        Uses regex replacement to support dot-notation keys (e.g. ${thresholds.cac_spike_ratio}).
        string.Template does not support dots in identifiers, so we use re.sub directly.
        Undefined variables are left as-is (safe_substitute semantics).
        Returns parsed dict, or None if brand binding not found.

        This renders Layer 1 (meta-pattern) with Layer 2 (brand binding) values
        so trigger conditions become concrete numbers for the trigger evaluator.
        """
        import yaml  # lazy import

        binding = self.get_brand_binding(merchant_id, meta_pattern_ref)
        if not binding:
            return None

        flat = _flatten_dict(binding)
        rendered = _render_template(meta_pattern_raw_yaml, flat)
        try:
            return yaml.safe_load(rendered)
        except Exception:
            log.warning(
                "[playbook_registry] Failed to parse rendered meta-pattern %s for %s",
                meta_pattern_ref, merchant_id, exc_info=True,
            )
            return None

    # ── Internal helpers ─────────────────────────────────────────────────────

    def _get_brand_binding_utility(
        self, merchant_id: str, playbook_id: str, action_id: str
    ) -> float | None:
        """Look up gmv_lift_prior from brand binding cache. Triggers lazy load."""
        binding = self.get_brand_binding(merchant_id, playbook_id)
        if not binding:
            return None
        priors = binding.get("action_utility_priors", {})
        action_prior = priors.get(action_id, {})
        raw = action_prior.get("gmv_lift_prior")
        if raw is None:
            return None
        return float(raw)

    def _clip_utility(self, value: float, playbook_id: str, action_id: str) -> float:
        """Clip utility to [0.0, _GMV_LIFT_MAX]. Log if clipping occurs."""
        clipped = max(0.0, min(value, _GMV_LIFT_MAX))
        if clipped != value:
            log.warning(
                "[playbook_registry] gmv_lift_prior %.4f clipped to %.4f for %s/%s — "
                "check gmv_lift_derivation in use case YAML",
                value, clipped, playbook_id, action_id,
            )
        return clipped

    def list_modules(self) -> list[str]:
        """Return all modules with registered playbooks."""
        self._ensure_loaded()
        return list(self._by_module.keys())

    def get_playbook(self, playbook_id: str) -> dict | None:
        """Return a playbook by id."""
        self._ensure_loaded()
        return self._by_id.get(playbook_id)
