# ADR-0008: Adopt LinUCB over Thompson Sampling for Bandit Exploration

## Status
Accepted (retroactive)
Date: 2026-04-09

## Context
The V3 scoring formula is:

```
Score = β1·U_base + β2·U_ucb − β3·Risk(Constraints)
```

The `U_ucb` term requires a contextual bandit algorithm to produce an
exploration bonus over the action space, conditioned on merchant state features
(`DecisionFeatureVector`). Multiple bandit algorithms were considered for
Phase 3 activation.

In B2B SaaS for CPG brands, each "arm pull" corresponds to a real merchant
action — spending ad budget, offering a discount, sending a campaign. Exploration
mistakes have direct business cost and are visible to the merchant. The algorithm
selection must balance exploration efficiency with:
1. Reproducibility: the same merchant must not see erratic recommendations
   within a short window (a week)
2. Explainability: the merchant and internal teams must be able to understand
   why a particular action ranked first
3. Safety: variance must be controllable — uncontrolled exploration against a
   risk budget can cause margin violations in live execution

## Decision
Adopt **LinUCB** (Li et al. 2010, "A Contextual-Bandit Approach to Personalized
News Article Recommendation", WWW 2010) as the Phase 3 bandit algorithm for the
U_ucb term.

LinUCB provides a deterministic upper confidence bound on each action's expected
reward, conditioned linearly on the context vector (`DecisionFeatureVector`).

Three properties drove the selection:

**1. Deterministic upper bound → reproducible merchant traces**
LinUCB's UCB is a deterministic function of the learned parameters (A matrix,
b vector) and the current context. Given identical inputs, the algorithm always
produces the same score. This makes merchant traces debuggable: when a merchant
asks "why did you recommend a discount this week but not last week?", the full
causal chain from feature vector to score is computable.

Thompson Sampling draws from a posterior distribution — two identical inputs can
produce different outputs. This makes audit traces probabilistic, complicating
both debugging and merchant trust.

**2. Controllable variance → prevents erratic same-merchant recommendations**
LinUCB's exploration is bounded by the confidence ellipsoid radius (the α
parameter). Setting α=0 gives pure exploitation; increasing α expands exploration
in proportion to uncertainty. The α parameter is exposed in `PolicyPack` as
`exploration_budget.bandit_alpha`, allowing operations to tune exploration
per-merchant.

Thompson Sampling's variance is determined by the posterior shape and is harder
to bound a priori. In a multi-action space with sparse reward signals (Phase 3
will have months of shadow-mode data before activation), Thompson Sampling can
assign high probability to poorly-estimated arms.

**3. Linear explainability → reverse-engineerable action weights**
LinUCB's reward model is `E[r] = θ^T · x` where x is the feature vector and θ
is the learned weight vector. Each feature's contribution to the score is
directly readable from θ. This enables explanations like "inventory pressure
contributed +0.12 to this action's score this week".

Neural contextual bandits and ensemble methods sacrifice this property. For CPG
operations teams who need to justify recommendations to brand owners, linear
explainability is a product requirement.

## Phase gate
`u_ucb = 0.0` is hardcoded in Phase 1 and Phase 2 (cold-start). LinUCB
activates only in Phase 3, after:
- 6+ months of `action_log` with outcome labels
- Statistical significance over the state distribution (see
  `bandit.py` TODO for arm pull threshold)

This is enforced by the scoring formula: when `u_ucb = 0.0`, the formula
reduces to `Score = β1·U_base − β3·Risk`, which is fully deterministic and
uses only expert priors.

## Alternatives Considered

**Thompson Sampling**: Standard Bayesian bandit with strong theoretical regret
bounds and good empirical performance in recommendation systems. Rejected for
B2B SaaS: probabilistic output breaks audit trails, and posterior sampling
variance is not directly bounded by a single tunable parameter. Would require
additional infrastructure (posterior sampling, variance clipping) that LinUCB
provides natively.

**ε-greedy**: Simple and widely understood. Rejected — random exploration at
rate ε can surface dominated actions and has no concept of uncertainty. In a
constrained action space where some actions have hard gates (margin_floor), ε
exploration can waste budget on known-ineligible actions.

**Neural contextual bandit (NeuralLinUCB, NeuralBandit)**: Better reward
approximation for non-linear merchant behavior. Rejected for Phase 3 — the
sample complexity for training a neural bandit far exceeds what 6 months of
CPG action logs can provide. The linear assumption is acceptable given that
merchant context (`DecisionFeatureVector`) is a 10-dimensional normalized
feature space. Revisit at Phase 4+ if non-linear patterns emerge in WSM data.

**Off-policy evaluation (IPS/DR)**: Using logged bandit data with inverse
propensity scoring. Not a replacement for the online algorithm — this is the
evaluation framework (planned for Phase 3 offline evaluation), not the
exploration strategy.

## Consequences

### Positive
- Deterministic scores enable full audit trails and debuggable merchant traces
- Single α parameter controls exploration intensity per-merchant via PolicyPack
- Linear θ weights provide native feature-level explanations
- Sample-efficient: LinUCB converges faster than Thompson Sampling in low-data
  regimes (Phase 3 early months)

### Negative
- Linear reward assumption may underfit non-linear merchant behavior
  (e.g., seasonality × margin sensitivity interactions). The
  `CrossModuleCorrelator` handles explicit cross-dimension interactions at the
  candidate level, but implicit non-linearities are not captured.
- Phase 3 regret bound depends on feature collinearity in `DecisionFeatureVector`
  — highly correlated features inflate the A matrix condition number

### Neutral
- `u_ucb = 0.0` in Phase 1–2 means this decision has no current runtime impact.
  The algorithm is implemented in `layer2_decision/pillar2_ml/bandit.py` as a
  stub (all methods TODO Phase 3).

## When to Revisit
- If WSM data (Phase 3+) shows reward function non-linearity that linear θ
  cannot capture: evaluate NeuralLinUCB with a warm-start from LinUCB weights
- If multiple merchants accumulate enough data for federated learning: evaluate
  whether a shared prior across merchants outperforms per-merchant θ
- If Thompson Sampling's audit trail problem can be solved by deterministic
  posterior sampling (fixed seed per merchant-week): reconsider

## References
- Li, L., Chu, W., Langford, J., Schapire, R. (2010). A contextual-bandit
  approach to personalized news article recommendation. WWW 2010.
- `V3/src/decision_engine/layer2_decision/pillar2_ml/bandit.py` — stub implementation
- `V3/src/decision_engine/layer2_decision/scoring.py` — u_ucb consumption in formula
- `V3/src/decision_engine/layer2_decision/pillar1_kg/policy_pack.py` — exploration_budget.bandit_alpha
- `V3/CLAUDE.md` — ML Phase Gates section
- `V3/docs/PHASE_ROADMAP.md` — Phase 3 Learning Fabric section
