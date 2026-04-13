# How to Work With V3 — Claude Code Collaboration Templates

## Purpose
This document is the operational manual for working on V3 with Claude Code (or any future AI agent). It exists so that any contributor — current team, new hires, future Claude Code sessions — can produce consistent, governance-compliant changes without re-learning the workflow each time.

The governance framework (ADRs, PHASE_ROADMAP, contract tests, architecture invariants) is in place. This document is the final piece: **how to actually use that framework day-to-day**.

---

## Core Principle

**The governance framework is not automatic.** Claude Code does not spontaneously check ADRs or run the EVOLUTION_GUIDE workflow. You must explicitly invoke it every time you start work.

This document gives you four templates that cover every common scenario. Pick the right one, copy it, paste it into Claude Code, fill in the blanks, send.

---

## Decision Tree: Which Template to Use

```
New Claude Code session opens
        │
        ▼
ALWAYS use Template D first (rebuild context)
        │
        ▼
Claude Code reports current V3 state
        │
        ▼
What do you want to do?
        │
        ├─ Want to check system health  ──────►  Template C (audit)
        │
        ├─ Want to add content
        │   (KG data, policy params,
        │    fixtures, bug fixes)        ──────►  Template B (content)
        │
        └─ Want to change architecture
            (new module, new typed
             object, new dependency,
             modify pipeline)            ──────►  Template A (architecture)
```

**Iron rule**: Every new session starts with Template D. Never skip it. Even if you "just want a quick fix," start with Template D — it takes 30 seconds and prevents Claude Code from acting on stale assumptions.

---

## Template A — Architecture Change

**Use when**: New module, new typed object, new cross-layer dependency, new external data source, modifying an existing contract, modifying pipeline execution order, introducing a new external dependency.

**Requires**: ADR + roadmap update + contract tests + implementation.

```
我要对V3做一个架构改动。在开始之前,请按顺序读以下文件建立上下文:

必读核心治理文件:
1. V3/docs/EVOLUTION_GUIDE.md — 五步流程说明
2. V3/docs/PHASE_ROADMAP.md — 当前所处阶段和已规划工作
3. V3/CLAUDE.md — 架构权威参考

必读ADR索引(快速扫一遍标题,理解已有决策):
4. V3/docs/adr/README.md

读完之后,严格按EVOLUTION_GUIDE的五步流程处理这次改动:

Step 1: 复制 docs/adr/template.md,起草新ADR(下一个可用编号)
        - Context、Decision、Alternatives、Consequences、When to revisit都要填
        - 如果你发现这次改动和某个已有ADR冲突,先告诉我,不要自己决定supersede

Step 2: 检查这次改动是否影响 contracts.py 里的任何typed object
        - 如果影响:列出哪些字段会变,影响哪些契约测试
        - 如果不影响:明确说"contracts unchanged"

Step 3: 找出这次改动在 PHASE_ROADMAP.md 的对应位置
        - 如果是Phase 1收尾、Phase 2 Track A、Phase 2 Track B、Phase 3:明确说哪一个
        - 如果在roadmap里找不到对应位置:停下来告诉我,我们要先讨论它该放在哪

Step 4: 先写测试再写实现
        - 新typed object → 契约测试在 tests/contracts/
        - 新模块 → 集成测试在 tests/e2e/ 或对应模块测试目录
        - 行为改动 → 更新对应测试
        - 任何架构边界改动 → 加架构不变式测试到 tests/architecture/

Step 5: 实现 + 跑全测试suite + 跑架构不变式测试
        - 任何已有测试fail必须停下来,不能删除或绕过
        - 任何架构不变式fail必须停下来,要么修代码要么写新ADR supersede

在动手之前,先把你的执行计划告诉我(包括ADR编号、影响的文件清单、新增测试清单),
我确认后再开始动手。

改动内容:
[在这里详细描述你要做什么、为什么要做、预期的产出]
```

---

## Template B — Content Change

**Use when**: KG data fill, playbook YAML edit, policy parameter tweak, new brand fixture data, bug fix, new test case, copy/text update.

**Requires**: No ADR, just do it (with safeguards).

```
我要给V3加内容,这是content级别的改动,不需要走architecture流程。

在开始之前,只需要读以下文件确认我的改动不会越界:
1. V3/docs/EVOLUTION_GUIDE.md 的 "Adding Business Content" 一节
2. V3/CLAUDE.md 中相关层的描述(如果改动涉及某一具体层)

判断准则(自我纠错检查):
- 如果这个改动需要新增ADR,停下来告诉我,这意味着它实际上是architecture改动
- 如果这个改动会修改任何 contracts.py 里的字段,停下来告诉我
- 如果这个改动会引入新文件到 src/ 而不是 fixtures/ 或 playbooks/,停下来告诉我
- 以上三种情况任何一种发生,都说明我的判断错了,要切换到Template A

如果以上都不触发,直接执行改动,然后跑测试确认绿。

改动内容:
[具体描述,例如"给BrightSkin fixture加一个新的signal字段叫inventory_sku_count,值是120"]
```

---

## Template C — Governance Audit (Monthly Safety Net)

**Use when**: Once a month, or before any major milestone (funding demo, partner review, phase transition).

**Requires**: Read-only inspection. No code changes.

```
对V3进行一次治理一致性审计。在开始之前读以下文件建立基线:
1. V3/docs/PHASE_ROADMAP.md
2. V3/docs/adr/README.md(ADR索引)
3. V3/docs/AUDIT_2026_04_09.md(上次审计基线)
4. V3/docs/SETUP_COMPLETE_2026_04_09.md(上次setup基线)

审计检查清单:

A. ADR完整性
   - 扫描 src/decision_engine/ 下所有模块,每个模块是否能映射到至少一个ADR?
   - 如果发现"代码存在但没有对应ADR"的孤儿模块,列出来
   - 检查每份ADR的Status是否还准确(Accepted的决策是否还在生效)

B. PHASE_ROADMAP准确性
   - 标记为[x]的项,在代码里是否真的实现了?
   - 标记为[ ]的项,是否实际已经偷偷做了一部分?
   - 标记的Phase归属是否还合理?

C. 契约一致性
   - tests/contracts/ 下是否覆盖了 contracts.py 的所有frozen Pydantic类?
   - 如果有新增类没有契约测试,列出来

D. 架构不变式
   - 跑 pytest tests/architecture/ -v
   - 列出所有不变式的当前pass/fail状态
   - 如果有fail的不变式,列出违规位置

E. 测试套件健康
   - 跑 pytest tests/ -v
   - 报告总测试数(对比上次setup_complete里的314)
   - 报告任何失败、跳过、警告

F. 文档交叉引用
   - CLAUDE.md 是否引用了所有10份ADR?
   - PHASE_ROADMAP是否引用了所有相关ADR?
   - 是否有"孤儿ADR"(写了但没在任何地方被引用)?

输出格式:
按A-F分节,每节明确"通过 / 警告 / 失败"。
最后给出一个"治理健康度评分"(0-100)和"建议优先处理的前三件事"。

不要修改任何文件,只做审计和报告。
```

---

## Template D — Session Bootstrap (Always First)

**Use when**: Every new Claude Code session, before any other template.

**Requires**: Read-only context rebuild.

```
这是一个新session。在我提出任何具体需求之前,请先建立V3的完整上下文。
按顺序读以下文件:

核心定位:
1. V3/CLAUDE.md(架构权威参考,约5分钟阅读量)

当前状态:
2. V3/docs/PHASE_ROADMAP.md(我们现在处于哪个Phase)
3. V3/docs/SETUP_COMPLETE_2026_04_09.md(最近一次重大变更的快照)
4. V3/docs/AUDIT_2026_04_09.md(最近一次审计的基线状态)

治理框架:
5. V3/docs/EVOLUTION_GUIDE.md(改动流程)
6. V3/docs/adr/README.md(ADR索引,只看标题列表)

数据状态:
7. V3/docs/DATA_AND_LICENSE_STATUS.md(数据来源和license状况)

读完之后,用三句话向我汇报:
(1) V3目前处于哪个Phase的哪个阶段
(2) 最近一次重大变更是什么(从SETUP_COMPLETE推断)
(3) 是否有任何"待人工确认"的事项
    (从DATA_AND_LICENSE_STATUS和ADR的"unresolved questions"里找)

不要做任何实际改动。等我下一条消息给你具体任务。
```

---

---

## Template E — KG Content Translation (Partner Delivery)

**Use when**: Partner delivers a new batch of brand use cases / KG content to translate into V3.

**Requires**: No ADR (content change per EVOLUTION_GUIDE), but must follow SOP.

```
我要把partner交付的KG内容翻译进V3三层结构。在开始之前:
1. 读 V3/docs/playbook_authoring_sop.md (完整的10步工作流 + schema)
2. 读 V3/docs/adr/0011-three-layer-kg-playbook-structure.md (理解三层设计决策)
3. 扫一遍 V3/playbooks/meta/ (检查是否已有可复用的 meta-pattern)

然后严格按 SOP 的10步流程处理:

Step 0: 通读本批全部 use case — 不写任何 YAML
Step 1: 横向对比，识别新 meta-pattern vs 已有 meta-pattern 的 brand 实例
Step 2: Magic Number 铁律 — meta-pattern 零数字，所有阈值用 ${thresholds.key}
Step 3: 如果是新 meta-pattern → 写 playbooks/meta/{module}_{theme}.yaml
Step 4: 写 brand binding → playbooks/brands/{brand_slug}/{meta_pattern_ref}.yaml
Step 5: 计算 gmv_lift_prior (用 SOP Section 6 的公式，不是拍脑袋)
Step 6: 写 use case YAML → use_cases/{brand_slug}/{prefix}_{NNN}_{slug}.yaml
         (所有原始数字只存在这里 — Single Source of Truth)
Step 7: 整理 ambiguous 字段清单，集中问 Partner
Step 8: 检查 threshold_key 命名空间 (SOP Section 5)，新 key 加 introduced_at
Step 9: 跑 python scripts/kg_dryrun.py，必须 exit 0
Step 10: 确认新 trigger 的 calibration_status: partner_prior 已设置

文件命名:
- Meta-pattern: playbooks/meta/{module}_{theme}.yaml
- Brand binding: playbooks/brands/{brand_slug}/{meta_pattern_ref}.yaml
- Use case: use_cases/{brand_slug}/{prefix}_{NNN}_{slug}.yaml

本次要翻译的内容:
[粘贴 partner 的 prose 或 use case 文档]
```

**Key invariants for KG content:**
- meta-pattern YAML 里出现任何 magic number → 立刻停下，抽成 threshold_key
- brand binding 里出现任何原始证据数字 → 立刻停下，移到 use_cases/
- `gmv_lift_prior` > 0.25 → 不要写，会被 clip，检查 derivation 是否有误
- 新 threshold_key 未在 SOP Section 5 命名空间里 → 先 review 是否能复用已有 key

---

## Common Mistakes to Avoid

1. **Skipping Template D** — "我只是想做个小修改,不用先建立上下文" → 错。Claude Code在没有context的情况下会做出错误判断。30秒的Template D能防止30分钟的回滚。

2. **混用Template A和Template B** — "这个改动既不像架构也不像内容" → 用判断标准:你需要写"为什么这样做"的解释吗?需要 = A,不需要 = B。

3. **Architecture改动跳过Step 1的ADR** — "ADR可以后补" → 不行。ADR是Step 1的产出物,后补的ADR会忘记当时考虑过的alternatives,失去价值。

4. **不跑Template C** — "没出问题就不审计" → 治理drift是悄悄发生的。等出问题时已经太晚。每月一次,十分钟,养成习惯。

5. **改了content但触发了ADR警告还继续做** — Template B里的自我纠错检查触发时,要立刻停下来切换到Template A,不要硬着头皮继续。

---

## Quick Reference Card

| Scenario | Template | Time Cost |
|---|---|---|
| 开新session | D | 30秒 |
| 加KG数据/调参数/修bug | B | 5-15分钟 |
| 加新模块/新typed object | A | 30分钟-2小时 |
| 月度健康检查 | C | 10分钟 |

---

## Maintenance

This document itself is a living artifact. Update it when:
- A new common scenario emerges that doesn't fit any template
- A template causes consistent confusion and needs refinement
- A new governance file is added that needs to be included in Template D's reading list

Updates to this document do not require an ADR (it is operational guidance, not architecture). Just edit and commit.

---

**Last updated**: 2026-04-12