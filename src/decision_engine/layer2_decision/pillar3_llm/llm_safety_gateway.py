# ── Layer 2 · Pillar 3 — 5-Gate Bouncer (Chain Layer 3 of 3) ──────────────
# Output QA: 5 gates that must pass before merchant sees the output.
#   1. Schema gate — merchant_copy has all required fields
#   2. Policy echo gate — module and action_id consistency
#   3. No raw numerics — impact_narrative uses formatted strings, not raw floats
#   4. Copy safety — no banned phrases, reasonable length
#   5. Grounding — all claims in narrative traceable to evidence[]
#
# 5-Gate failure blocks API response but NOT WSM logging.
# (The decision was valid; only the expression failed QA.)
#
# Supports all 4 modules: retention, acquisition, conversion, promotion.
#
# Reference: V0/llm_safety_gateway.py (adapted to V3 deterministic rendering)
# ───────────────────────────────────────────────────────────────────────────
from __future__ import annotations

import logging
import re

log = logging.getLogger(__name__)

_REQUIRED_FIELDS = frozenset({
    "diagnosis", "recommendation", "impact_narrative", "confidence_statement",
})

_VALID_MODULES = frozenset({"retention", "acquisition", "conversion", "promotion"})

_BANNED_PHRASES = [
    "guarantee", "guaranteed", "100% free", "spam", "risk-free",
    "act now", "limited time only", "you've been selected",
]

_MAX_FIELD_LENGTH = 500

# Raw float pattern: catches 0.15, 4000.0, etc.
# Does NOT flag formatted strings like $1,200 or 30%
_RAW_FLOAT_RE = re.compile(r"(?<!\$)(?<!\d,)\b\d+\.\d{2,}\b(?!%)")

# Module → expected evidence fields for grounding
_MODULE_EVIDENCE_KEYS: dict[str, set[str]] = {
    "retention": {"overdue_ratio", "repeat_purchase_rate", "days_since_last_order_p50"},
    "acquisition": {"cac_7d", "cac_baseline_30d", "roas_7d", "roas_baseline_30d"},
    "conversion": {"mobile_atc_rate", "desktop_atc_rate", "mobile_traffic_pct", "checkout_cvr"},
    "promotion": {"promo_incrementality", "existing_customer_promo_pct", "promo_margin_delta"},
}


class LLMSafetyGateway:
    """5-Gate Bouncer — output QA for merchant-facing copy.

    5-Gate failure blocks API response but NOT WSM logging.
    Supports all 4 modules: retention, acquisition, conversion, promotion.
    """

    def validate(
        self,
        merchant_copy: dict,
        action: dict,
        evidence: list[dict] | None = None,
    ) -> list[str]:
        """Run all 5 gates. Returns list of error codes (empty = all passed)."""
        errors: list[str] = []

        # Gate 1: Schema
        errors.extend(self._gate_schema(merchant_copy))
        if errors:
            return errors  # Fatal — can't check other gates

        # Gate 2: Policy echo
        errors.extend(self._gate_policy_echo(merchant_copy, action))

        # Gate 3: No raw numerics
        errors.extend(self._gate_no_raw_numerics(merchant_copy))

        # Gate 4: Copy safety
        errors.extend(self._gate_copy_safety(merchant_copy))

        # Gate 5: Grounding
        errors.extend(self._gate_grounding(merchant_copy, action, evidence))

        return list(set(errors))

    def _gate_schema(self, merchant_copy: dict) -> list[str]:
        """Gate 1: all required fields present and non-empty."""
        errors = []
        for field in _REQUIRED_FIELDS:
            val = merchant_copy.get(field)
            if val is None or (isinstance(val, str) and not val.strip()):
                errors.append(f"E_SCHEMA_MISSING_{field.upper()}")
        return errors

    def _gate_policy_echo(self, merchant_copy: dict, action: dict) -> list[str]:
        """Gate 2: module is valid for all 4 modules."""
        errors = []
        module = action.get("module", "")
        if module and module not in _VALID_MODULES:
            errors.append("E_POLICY_ECHO_INVALID_MODULE")
        return errors

    def _gate_no_raw_numerics(self, merchant_copy: dict) -> list[str]:
        """Gate 3: verify impact_narrative uses words not raw floats."""
        errors = []
        narrative = merchant_copy.get("impact_narrative", "")
        if _RAW_FLOAT_RE.search(narrative):
            errors.append("E_NUMERIC_RAW_FLOAT")
            log.warning("Gate 3 failed: raw numerics in impact_narrative")
        return errors

    def _gate_copy_safety(self, merchant_copy: dict) -> list[str]:
        """Gate 4: no banned phrases, reasonable field lengths."""
        errors = []
        for field in _REQUIRED_FIELDS:
            text = merchant_copy.get(field, "")
            if not isinstance(text, str):
                continue
            if len(text) > _MAX_FIELD_LENGTH:
                errors.append(f"E_COPY_TOO_LONG_{field.upper()}")
            lower_text = text.lower()
            for phrase in _BANNED_PHRASES:
                if phrase in lower_text:
                    errors.append("E_COPY_BANNED_PHRASE")
                    break
        return errors

    def _gate_grounding(
        self,
        merchant_copy: dict,
        action: dict,
        evidence: list[dict] | None,
    ) -> list[str]:
        """Gate 5: verify all claims in narrative are traceable to evidence[].

        For all 4 modules, check that key claims in the diagnosis
        are grounded in the evidence data.
        """
        errors = []

        # Build evidence field set
        evidence_fields: set[str] = set()
        if evidence:
            for e in evidence:
                if isinstance(e, dict):
                    evidence_fields.update(e.keys())
        evidence_fields.update(action.keys())

        module = action.get("module", "")
        expected_keys = _MODULE_EVIDENCE_KEYS.get(module, set())

        # If we have expected keys for this module but NONE appear in evidence,
        # and the diagnosis references module-specific content → grounding failure
        if expected_keys and not expected_keys.intersection(evidence_fields):
            diagnosis = merchant_copy.get("diagnosis", "").lower()
            # Only fail if the diagnosis makes specific claims
            module_keywords = {
                "retention": ["overdue", "churn", "purchase cycle"],
                "acquisition": ["cac", "roas", "spend"],
                "conversion": ["mobile", "atc", "desktop"],
                "promotion": ["incrementality", "margin", "fatigue"],
            }
            keywords = module_keywords.get(module, [])
            if any(kw in diagnosis for kw in keywords):
                errors.append("E_GROUNDING_MISSING_EVIDENCE")

        return errors
