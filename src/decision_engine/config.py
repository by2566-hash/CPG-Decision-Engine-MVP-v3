from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # ── Infrastructure ───────────────────────────────────────────────
    postgres_dsn: str = "postgresql://postgres:postgres@localhost:5432/decision_engine"
    redis_url: str = "redis://localhost:6379/0"
    shopline_app_secret: str = "replace_me"
    shopline_api_version: str = "v20260301"

    # ── Scoring weights ──────────────────────────────────────────────
    default_bandit_alpha: float = 0.25
    beta1: float = 0.65
    beta2: float = 0.25
    beta3: float = 0.10

    # ── Planner ──────────────────────────────────────────────────────
    enable_llm_planner: bool = False
    policy_ttl_days: int = 8

    # ── Rollout feature flags ────────────────────────────────────────
    shadow_mode: bool = True                      # Log decisions but don't act
    low_risk_auto_actions: bool = False            # Auto-execute low-risk actions
    emergency_auto_actions: bool = False           # Auto-execute emergency actions
    autopilot_scope: List[str] = []                # Verticals enabled for autopilot

    # ── Kill-switch & rollback ───────────────────────────────────────
    kill_switch: bool = False                      # Hard stop: disables all decisions
    max_constraint_violation_pct: float = 0.15     # Abort if violations exceed 15%
    rollback_to_version: str = ""                  # Force use of specific policy version

    # ── Readiness thresholds ─────────────────────────────────────────
    min_data_freshness_hours: int = 24             # Max age of merchant state data
    min_bandit_freshness_hours: int = 168          # Max age of bandit model (7d)
    min_policy_freshness_hours: int = 192          # Max age of planner policy (8d)

    # ── MSM thresholds (Layer 1 — MerchantStateMachine) ──────────────
    # All MSM thresholds are configured here, never hardcoded in msm.py.
    # Acquisition dimension: CAC_7d relative to baseline
    msm_cac_degrading_multiplier: float = 1.15     # Used by MSM: acquisition → DEGRADING
    msm_cac_critical_multiplier: float = 1.35      # Used by MSM: acquisition → CRITICAL
    # Conversion dimension: mobile add-to-cart vs desktop ratio
    msm_mobile_atc_watch_ratio: float = 0.70       # Used by MSM: conversion → WATCH
    msm_mobile_atc_degrading_ratio: float = 0.50   # Used by MSM: conversion → DEGRADING
    # Retention dimension: overdue ratio thresholds
    msm_overdue_watch_threshold: float = 1.20      # Used by MSM: retention → WATCH
    msm_overdue_degrading_threshold: float = 1.50  # Used by MSM: retention → DEGRADING
    msm_overdue_critical_threshold: float = 1.80   # Used by MSM: retention → CRITICAL
    # Promotion dimension: incrementality floor
    msm_promo_incrementality_watch: float = 0.40   # Used by MSM: promotion → WATCH
    msm_promo_incrementality_degrading: float = 0.25  # Used by MSM: promotion → DEGRADING

    # MSM urgency and acceleration thresholds (extracted from MSM, never hardcode there)
    msm_roas_decline_ratio: float = 0.9              # Used by MSM: ROAS decline check
    msm_mobile_traffic_majority_threshold: float = 0.5  # Used by MSM: conversion → WATCH guard
    msm_urgency_transition_bonus: float = 0.1        # Used by MSM: urgency bonus on state worsening
    msm_urgency_acceleration_bonus: float = 0.1      # Used by MSM: urgency bonus on signal acceleration
    msm_cvr_acceleration_threshold: float = -0.05    # Used by MSM: CVR 3d drop threshold
    msm_overdue_acceleration_multiplier: float = 1.2  # Used by MSM: overdue acceleration multiplier

    # ── Alert engine (Layer 1 — AlertEngine) ─────────────────────────
    alert_polling_interval_seconds: int = 300      # Used by AlertEngine: polling cadence
    alert_critical_auto_push: bool = True          # Used by AlertEngine: auto-push on CRITICAL

    # ── Impact calculator (Layer 3 — ImpactCalculator) ───────────────
    impact_calculator_use_benchmark_fallback: bool = True  # Used by ImpactCalculator: fall back to industry benchmarks
    impact_confidence_floor: float = 0.30          # Used by ImpactCalculator: minimum confidence threshold

    # ── Benchmark engine (Layer 3 — BenchmarkEngine) ─────────────────
    benchmark_min_peer_count: int = 5              # Used by BenchmarkEngine: minimum peers for valid comparison

    # ── Billing (Phase 2 activation) ─────────────────────────────────
    performance_fee_rate: float = 0.10             # Used by billing: % of outcome_delta charged
    performance_fee_enabled: bool = False           # Used by billing: Phase 2 toggle (off in Phase 1)

    # ── Approval gate (Layer 3 — MerchantApprovalGate) ───────────────
    approval_required_discount_threshold: float = 0.15   # Used by ApprovalGate: discount > 15% needs approval
    approval_required_budget_daily_usd: float = 1000.0   # Used by ApprovalGate: budget > $1k/day needs approval
    rollback_ttl_hours: int = 48                   # Used by RollbackRegistry: undo window in hours


settings = Settings()
