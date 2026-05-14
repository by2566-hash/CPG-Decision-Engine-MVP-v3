# CPG Decision Engine V3 — Architecture Reference

## Governance References
- **Architecture Decision Records**: `docs/adr/` — 13 ADRs (0001–0013), every major decision documented with rationale and alternatives
- **Phase Roadmap**: `docs/PHASE_ROADMAP.md` — single source of truth for planned work (Phase 1, Phase 2 dual-track, Phase 3)
- **Contract Tests**: `tests/contracts/` — enforce typed object invariants
- **Architecture Invariant Tests**: `tests/architecture/` — detect architectural drift
- **End-to-End Demo**: `tests/e2e/test_brightskin_walkthrough.py` and `scripts/demo_brightskin.py`
- **Evolution Guide**: `docs/EVOLUTION_GUIDE.md` — how to make architectural changes

When making architectural changes, follow the workflow in
`docs/EVOLUTION_GUIDE.md`: write ADR → update roadmap → update contract
tests if types change → implement.

Key ADRs: PolicyDecision [0001] · Feature Plane [0005] · Phase 2 dual-track [0006] ·
Cross-layer dependency [0007] · LinUCB [0008] · Evidence Graph Snapshot [0009] ·
Data Source Facade [0010] · Three-Layer KG [0011] · match_playbook contract [0012] ·
MSM-state routing [0013]

---

## Core Philosophy (Non-Negotiable)
1. **Determinism over Probability**: Rules first → Statistical models second → Bandit last
2. **Explainability IS the product**: Every output traces data point → causal chain → decision basis
3. **Human confirmation before execution**: Recommend → Approve → Execute → Record → Rollback

---

## 6-Layer Architecture

### L0 · Signal Plane
**职责**: 接入、标准化、落地原始业务信号。只做数据事实化，零决策逻辑。
- 输入: Shopline / Shopify / Meta Ads / GA4 / inventory / catalog / order / campaign APIs
- 产物: raw events, normalized facts, snapshot tables, source metadata
- 代码位置: `layer0_data/`

### L1 · Merchant State Plane
**职责**: 把原始信号压成可路由的决策状态。
- 产物: 4D MSM state, alerts, anomaly flags, health transitions
- 设计原则: 4 dimensions × 4 states (HEALTHY / WATCH / DEGRADING / CRITICAL)
- **关键约束**: MSM 是 decision routing state，不是完整 feature representation。
  - 适合: routing（把 candidate 路由到正确 module）和 explainability
  - 不适合: 作为模型的唯一输入 context
- 代码位置: `layer1_msm/`

### L2 · Domain World Model (KG Layer)
**职责**: 提供 typed world model + evidence graph，作为 candidate expansion context。
- KG 做三件事: (1) world model (entities + relations), (2) evidence graph (哪条 metric 支持哪个 action), (3) candidate expansion context
- KG 不做四件事: 不做最终规则执行, 不做 feature store, 不存全文文档作为主结构, 不直接做训练数据库
- Phase 1 现状: `commerce_graph.py` 是 KG stub，`playbook_registry.py` 承载 playbook templates
- Phase 2 目标: typed entity graph (Merchant/SKU/Campaign/Segment) + evidence graph + document compiler → 三路输出(graph facts / policy candidates / retrieval chunks)
- 代码位置: `layer2_decision/pillar1_kg/`

**物理结构 vs 概念定位 (重要)**:
- 物理结构: 三个 pillar (pillar1_kg / pillar2_ml / pillar3_llm) 目前都在 `layer2_decision/` 目录下。
- 概念定位: V3.5 架构把 L2 定义为 Domain World Model——只做实体图、关系图、证据链。规则执行归 L3 ConstraintEngine，特征计算归 Feature Plane，训练数据归 L5 Learning Fabric。
- 物理和概念的完整对齐将在 Phase 2 Track B 完成 (LLM Renderer 迁移到 `layer4_serving/`，L3 physical split)。参见 ADR-0003。

**命名对照表** (pillar 是历史命名，V3.5 概念名如下):

| V3 物理目录 | V3.5 概念名 | ADR |
|------------|------------|-----|
| `pillar1_kg/` | KG / Domain World Model | ADR-0003 |
| `pillar2_ml/` | ML / Anomaly + Bandit | ADR-0008 |
| `pillar3_llm/` | LLM Renderer + Safety Gate | ADR-0002, ADR-0003 |

### L3 · Decision Core [see ADR-0002, ADR-0003]
**职责**: 完整的 decisioning 流程，5 个子模块严格顺序执行。

**L3.1 Candidate Proposal** (KG-Driven)
- 输入: MSM states + alerts + KG/playbook templates
- 输出: `RawCandidate[]`
- 说明: 生成 raw action candidates，不是最终 decision card

**L3.2 Correlation & Conflict Resolution**
- 输入: `RawCandidate[]`
- 输出: `CorrelatedCandidate[]`
- 组件: CrossModuleCorrelator (处理显式 cross-dimension interactions)
- 例: "conversion 也在 degrading 时，不要增加 ad budget"

**L3.3 Policy Evaluation** [see ADR-0001]
- 输入: candidate + merchant policy + hard constraints + approval rules
- 输出: `PolicyDecision`
- 接口定义:
  ```python
  PolicyDecision {
    eligible: bool
    hard_reject: bool
    risk_penalty: float        # 按 violation 类型加权，非简单 count
    violations: list[str]      # 格式: "constraint_name:detail"
    requires_approval: bool
    rollback_required: bool
    policy_version: str
  }
  ```
- 架构原则: policy 是独立决策接口，不散落在不同模块里
- 代码位置: `layer3_value/constraints.py` → 升级为统一 PolicyDecision 接口

**L3.4 Scoring & Ranking**
- 输入: `CorrelatedCandidate` + `PolicyDecision` + `DecisionFeatureVector`
- 输出: `ScoredCandidate[]`
- 公式: `Score = β1·U_base + β2·U_ucb − β3·Risk`
  - U_base: 来自 playbook priors + KG context + benchmark priors
  - U_ucb: 来自 bandit / learning model (Phase 3)；Phase 1 cold-start: u_ucb = 0.0
  - Risk: 来自 Policy Engine (L3.3)，不直接消费 constraints.py
- β weights: 来自 PolicyPack.policy_weights，从不 hardcode

**L3.5 Verification**
- 输入: Top-K `ScoredCandidate[]`
- 输出: `VerifiedDecision[]`
- 组件: DecisionVerifier (deterministic hard gate，整个系统的 safety shell)
- 三层验证链严格顺序: DecisionVerifier → LLM Renderer → 5-Gate Bouncer
  - Rule 1: DecisionVerifier 失败 → 阻止 LLM rendering (final_score = -inf)
  - Rule 2: 5-Gate 失败 → 阻止 API response，不阻止 WSM logging

- 代码位置: `layer2_decision/pillar3_llm/decision_verifier.py`

### L4 · Experience & Delivery Plane [see ADR-0009]
**职责**: 把 verified decision 转换为可展示、可审批、可缓存的 card。不做 decisioning。

**Evidence Graph Snapshot** [see ADR-0009]:
- pipeline 在 Step 8b 为 top-3 eligible candidates 生成 `EvidenceGraphSnapshot`
- Snapshot 聚合从 L1 到 L3 的因果链: L1_State → L2_KG → L3_Constraint → L3_Scoring → L3_Verification
- `LLMRenderer.render_from_snapshot(snapshot)` 是新的渲染路径 — LLM 只做 "translate this logic chain"，不添加 trace 外的事实
- 旧路径 `render(verified_decision)` 保持不变 (backwards compatible)
- Snapshot 也持久化到 L5 WSM，用于 "为什么 bandit 学到了这个 policy" 的离线分析

**L4.1 Explanation Retrieval**: 从 playbook / evidence graph 拉解释素材
**L4.2 Renderer**: deterministic template first，LLM API later；只接收 VerifiedDecision
**L4.3 Card QA / Bouncer**: schema validation, policy echo, evidence grounding, tone/copy safety
**L4.4 Serving**: 写 cache，API serving，approval UX

- Fast Plane 原则: **只 serve PublishedCard 和 execution commands，从不暴露 raw candidates 或 unverified decisions**
- Fast Plane 不调用 pipeline.run_once()
- 代码位置: `layer4_serving/` (renderer/bouncer 当前在 `layer2_decision/pillar3_llm/`，Phase 2 迁移)

### L5 · Learning Fabric
**职责**: 记录、归因、更新。不直接参与在线执行。WSM = learning substrate / decision log / outcome attribution fabric。

**L5.1 Decision Log**: candidate set, chosen recommendation, policy decision, verification outcome, rendered card id, merchant response
**L5.2 Execution Log**: approved?, executed?, rollback available?, rollback invoked?, connector response
**L5.3 Outcome Log**: proxy reward, final reward, timing window, confidence, causal baseline / counterfactual
**L5.4 Feature History**: 为 bandit / impact estimator / offline evaluation 提供历史特征

- Phase 1 现状: 单表 `wsm_transitions_v3` 合并存储；函数命名按 log 类型区分
  - 写入接口: `db_client.py` 直接操作（`insert_wsm_transition`, `update_wsm_execution` 等）
  - `wsm_client.py` 已于 Phase 1 移除（async 设计与系统同步架构不符，功能由 db_client 承担）
- Phase 3 目标: 按 L5.1-L5.4 分表（需要真实执行数据积累后才有意义）
- 代码位置: `layer5_wsm/`

---

## Core Data Objects (强制引入的类型契约)

下列 8 个对象是系统的骨架，严禁用 plain dict 替代：

| 对象 | 来源层 | 状态 |
|------|--------|------|
| `StateSnapshot` (= MerchantStateVector) | L1 | ✅ 已存在 |
| `RawCandidate` | L3.1 | ✅ 已定义 (Pydantic, frozen=True) |
| `CorrelatedCandidate` | L3.2 | Phase 3 (L3 sub-module split 后) |
| `PolicyDecision` | L3.3 | ✅ 已完成 [→ADR-0001] |
| `ScoredCandidate` | L3.4 | ✅ 已定义 (Pydantic, frozen=True) |
| `VerifiedDecision` | L3.5 | Phase 2 Track B (L3 split 时) |
| `EvidenceGraphSnapshot` | L3→L4 boundary | ✅ 已完成 [→ADR-0009] |
| `DecisionCard` | L4.2 | ✅ 已存在 (Pydantic) |
| `PublishedCard` | L4.4 | 用 DecisionCard + cache metadata |

---

## Feature Plane [see ADR-0005] (逻辑概念，不单独编号)

解决"被模型消费的数字分散在 signals dict / MSM / scoring inputs 之间"的问题。

```python
DecisionState:              # MSM routing — 离散状态，来自 L1
  acquisition_state         # "HEALTHY" | "WATCH" | "DEGRADING" | "CRITICAL"
  conversion_state
  retention_state
  promotion_state
  active_alerts

DecisionFeatureVector:      # 模型输入 — 连续数值，来自 L0 + L2
  inventory_days
  margin_pct
  repeat_rate_7d
  cvr_7d / cvr_30d
  promo_redemption_30d
  stock_pressure_score
  churn_score
  seasonality_index
  benchmark_gap_score
```

职责分离原则:
- MSM 负责 routing
- FeatureVector 负责数值计算
- KG 负责 context
- Policy 负责边界

---

## CPG Hard Constraints (从不被 LLM 或 ML 覆盖)

1. **Margin floor**: post-discount margin >= 0.15 always
2. **Discount = last resort**: REMINDER before DISCOUNT
3. **Incrementality required**: no discount without uplift attribution
4. **Cold prospect gate**: no discount to first-time visitors
5. **Attribution windows**: Retention 7d / Acquisition 30d / Promotion 14d / Conversion instant
6. **Inventory gate**: no promotion if inventory_days < safety threshold
- Rollback TTL: every write action has undo endpoint，48h window

---

## ML Phase Gates (严禁提前部署) [Phase 2 dual-track: see ADR-0006]

- Phase 1: `anomaly_detector.py` (Isolation Forest，无需训练数据)
- Phase 2: `regression_model.py` (XGBoost，需 3 个月 order history)
- Phase 3: `bandit.py` LinUCB (需 6 个月 action_log with outcomes) [see ADR-0008]

在 Phase 1–2，`u_ucb = 0.0`，scoring 退化为 `Score = β1·U_base − β3·Risk`。

---

## KG / Policy Pack 解耦原则

- KG/Playbook YAML: platform-level，稳定(weeks/months)，domain expert 管理
- Policy Pack: merchant-level，按周变化，operations 管理
- 严禁在 policy_pack.py 里 import playbook 逻辑，反之亦然

---

## WSM Required Fields (从 Day 1 起必须存在)

`was_executed`, `executed_at`, `execution_params`, `baseline_snapshot`,
`outcome_delta`, `verification_chain`, `impact_estimate`, `counterfactual`,
`reward_status` (pending→proxy→final), `module`, `msm_dimension`, `msm_state`,
`urgency_score`, `planner_policy_version`

---

## Cross-Layer Dependency Note

`constraints.py` 住在 Layer 3 (Action Safety)，被 Layer 2 scoring 作为 Risk(Constraints) term 消费。这是**故意设计**:
- Safety enforcement 是它的主身份 (L3)
- Penalty signal 是它的次要角色 (consumed by L2)

---

## V0/V2 Reference Rules

- V0: 已测试，直接参考，谨慎改编
- V2: 测试状态未知，只读逻辑，不 copy-paste，验证后再用
- 每个复用组件必须被显式验证

---

## What We Do NOT Build in V3

- Auto-execution without merchant approval
- Neptune migration (DynamoDB sufficient)
- Cross-vertical expansion beyond CPG
- Customer×Product granularity WSM (merchant-level only)
- Bandit before Phase 3 data threshold
- OPA integration (PolicyDecision Pydantic model is sufficient for Phase 1-2)
- Lean/formal verification tooling
