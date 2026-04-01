# ── Layer 2 · Pillar 2 — Anomaly Detector (Phase 1 ML) ──────────────────────
# Phase 1 ML component: Isolation Forest anomaly detection
# No training data required — unsupervised
# Outputs: anomaly_score (0-1), signal_confidence (0-1)
#
# Active from Day 1 — the only ML component in Phase 1.
#
# TODO Phase 2: Replace z-score proxy with trained sklearn IsolationForest
# ───────────────────────────────────────────────────────────────────────────
from __future__ import annotations

import logging
import math

log = logging.getLogger(__name__)

# Expected ranges for commerce metrics (used by z-score proxy)
# Keys map to signal names; values are (mean, std_dev) tuples.
EXPECTED_RANGES = {
    "cac_vs_baseline_ratio":    {"mean": 1.00, "std": 0.15},
    "roas_7d":                  {"mean": 2.50, "std": 0.80},
    "overdue_ratio":            {"mean": 1.20, "std": 0.30},
    "mobile_atc_desktop_ratio": {"mean": 0.85, "std": 0.15},
    "promo_incrementality":     {"mean": 0.55, "std": 0.15},
    "repeat_purchase_rate":     {"mean": 0.28, "std": 0.08},
    "checkout_cvr":             {"mean": 0.035, "std": 0.010},
}


class AnomalyDetector:
    """Phase 1: z-score proxy for Isolation Forest anomaly detection.

    For each numeric signal, computes deviation from expected range.
    Returns anomaly_score (0=normal, 1=highly anomalous) and signal_confidence.
    """

    def detect(self, signals: dict) -> dict:
        """Phase 1: Use statistical z-score as proxy for Isolation Forest.

        For each numeric signal, compute deviation from expected range.
        Return {
            "anomaly_score": float,       # 0=normal, 1=highly anomalous
            "signal_confidence": float,   # how confident we are in the signals
            "anomalous_signals": list[str]
        }
        """
        # Phase 1 ML component: z-score proxy (statistical deviation detection)
        # No training data required — uses hardcoded CPG industry baselines
        # Phase 2: Replace with trained Isolation Forest model
        anomalous_signals = []
        checked_signals = 0

        for key, value in signals.items():
            if not isinstance(value, (int, float)):
                continue

            if key in EXPECTED_RANGES:
                checked_signals += 1
                stats = EXPECTED_RANGES[key]
                mean = stats["mean"]
                std = stats["std"]

                if std > 0:
                    z_score = abs(value - mean) / std
                    if z_score > 2.0:
                        anomalous_signals.append(key)

        num_signals = len(signals)
        signal_confidence = float(checked_signals) / num_signals if num_signals > 0 else 0.0
        anomaly_score = float(len(anomalous_signals)) / checked_signals if checked_signals > 0 else 0.0

        return {
            "anomaly_score": anomaly_score,
            "signal_confidence": signal_confidence,
            "anomalous_signals": anomalous_signals,
        }
