# CPG Decision Engine V3 — Architecture Reference

## Core Philosophy (Non-Negotiable)
1. Determinism over Probability: Rules first → Statistical models second → Bandit last
2. Explainability IS the product: data point → causal chain → decision basis
3. Human confirmation before execution: Recommend → Approve → Execute → Record → Rollback

## 6-Layer Architecture
- Layer 0: Data Foundation (connectors + event store + commerce graph)
- Layer 1: Merchant State Machine — 4 dimensions × 4 states + Alert Engine
- Layer 2: Tri-Pillar Decision Engine (KG + ML + LLM) + Cross-Module Correlator
- Layer 3: Value Intelligence + Action Safety (ImpactCalculator, BenchmarkEngine,
           FeedbackCollector, WeeklyPlanner, RollbackRegistry, MerchantApprovalGate, Constraints)
- Layer 4: Serving & Execution — Two-Plane Runtime (Deep Plane + Fast Plane)
- Layer 5: World State Model — S/A/R/S' learning substrate

## Three-Layer Verification Chain (strict order, no skipping)
  DecisionVerifier → LLM Renderer (Mouth) → 5-Gate Bouncer
  Rule 1: DecisionVerifier failure → blocks LLM rendering (final_score = -inf)
  Rule 2: 5-Gate failure → blocks API response, does NOT block WSM logging

## Scoring Formula (LinUCB — Li et al. 2010 WWW)
  Score = β1·U_base(KG) + β2·U_ucb(Bandit) − β3·Risk(Constraints)
  - β weights: from PolicyPack.policy_weights (never hardcoded)
  - Phase 1 cold-start: u_ucb = 0.0 when arm.num_pulls == 0
  - Phase 1 effective formula: Score = β1·U_base − β3·Risk

## KG vs Policy Pack — Always Decoupled
  - KG/Playbook YAML: platform-level, stable (weeks/months), domain expert manages
  - Policy Pack: merchant-level, changes weekly, operations manages
  - NEVER import playbook logic inside policy_pack.py and vice versa

## ML Phase Gates (never deploy before prerequisites)
  - Phase 1: anomaly_detector.py (Isolation Forest, no training data needed)
  - Phase 2: regression_model.py (XGBoost, needs 3 months order history)
  - Phase 3: bandit.py LinUCB (needs 6 months action_log with outcomes)

## WSM Required Fields (all must exist from Day 1)
  was_executed, executed_at, execution_params, baseline_snapshot,
  outcome_delta, verification_chain, impact_estimate, counterfactual,
  reward_status (pending→proxy→final), module, msm_dimension, msm_state,
  urgency_score, planner_policy_version

## CPG Hard Constraints (never overridden by LLM or ML)
  - Margin floor: post-discount margin >= 0.15 always
  - Discount = last resort: REMINDER before DISCOUNT
  - Incrementality required: no discount without uplift attribution
  - Cold prospect gate: no discount to first-time visitors
  - Attribution windows: Retention 7d / Acquisition 30d / Promotion 14d / Conversion instant
  - Rollback TTL: every write action has undo endpoint, 48h window

## Cross-Layer Dependency Note (for reviewers)
  constraints.py lives in Layer 3 (Action Safety) but is consumed by Layer 2
  scoring as the Risk(Constraints) term. This is intentional.
  Safety enforcement is its primary identity (Layer 3).
  Penalty signal is its secondary role (consumed by Layer 2 scoring).

## V0/V2 Reference Rules
  - V0: tested and trusted — reference freely, adapt carefully
  - V2: uncertain test status — read for logic only, never copy-paste without checking
  - Every reused component must be explicitly verified

## What We Do NOT Build in V3
  - Auto-execution without merchant approval
  - Neptune migration (DynamoDB sufficient)
  - Cross-vertical expansion beyond CPG
  - Customer×Product granularity WSM (merchant-level only)
  - Bandit before Phase 3 data threshold
  - Lean/formal verification tooling
