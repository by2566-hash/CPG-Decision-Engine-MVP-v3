# Decision Engine V3 — KG & Use Case 协作方式说明

**文档类型**: KG/Use Case Partner 沟通文档
**对象**: KG / Use Case Partner
**版本**: v1.0 (2026-04-12)
**作者**: Yubo

---

## 状态更新

**2026-04-14 update on Wandering Bear scope**: wb_003 和 wb_006 在 audit 中
被识别为 pre-three-layer 翻译，已 quarantine 到 `use_cases/wandering_bear/_legacy/`。
这两个 case 当前不在 active KG 系统中。下方对 wb_006 阈值的问题（库存安全天数、
SKU 集中度）暂时降级为 **non-urgent** —— 答案在我们决定是否激活 wb_006 时
才需要。如果 Partner 在下次同步时主动提及，记下答案但不要把它们加进 active
brand binding。

---

## 第一件事：你的内容是怎么进入系统的

我没有用 LLM 去"翻译"你的内容。

这件事我认为需要明确说清楚，因为很多人听到"AI decision engine"就会以为我把你的文档扔进 GPT 让它生成系统配置。

**实际做法是这样的**：

你写的每一个 use case，我都逐字阅读，理解其中的商业逻辑、数据结构、因果链，然后我写代码、设计数据结构，**手动**把它翻译成系统能执行的格式。这个过程需要我理解：

- 这个 issue 的根本原因是什么（mix problem？measurement artifact？channel routing？）
- 观察到的数据是触发条件的阈值还是结果数字
- 这个 action 的商业意图是防止错误动作，还是直接产生 GMV，两者的量化方式完全不同
- 这个 issue 在其他品牌身上是否也会出现（如果是，它变成一个可复用的 meta-pattern；如果不是，它只是这个品牌的专属配置）

以 WB 为例，你提供的 6 个 issue，我做了以下工作：

| 你的 issue | 我的翻译工作 |
|-----------|------------|
| PM SKU 稀释订阅率 | 识别为 mix_problem 根因，设计 `conversion_subscription_mix` 这个可复用 meta-pattern，提取 3 个阈值变量 |
| ShopCash 分母问题 | 识别为 measurement_artifact，作为同一 meta-pattern 下的第二个 action（`FIX_DENOMINATOR`） |
| Evergreen 命名测试 | 识别为 conversion → COPY_TEST 类型，记录核心 metric 是 ATC share 而非最终 CVR |
| Brand vs DR CPA 分拆 | 识别为 acquisition → budget allocation 问题，DR CPA -11.8% 的数字作为 gmv_lift_prior 的推导输入 |
| Meta 广告投放目的地路由 | 识别为 acquisition → channel routing，CAC -17.4% 直接转化为 gmv_lift_prior=0.12 |
| 库存预警 + 广告收缩 | 识别为 acquisition → inventory-constrained spend reduction，保留了你的 "5.89% 广告削减，CAC -8%" 的因果链 |

你的原稿完整保存在 `partner_drafts/kg_partner/wandering_bear/`，不会被修改。

---

## 第二件事：我想请你看一下翻译结果

你是这些内容商业逻辑的最终裁判。

我的翻译过程中做了大量判断，每一个判断都可能和你的本意有偏差。最重要的几类判断是：

**1. 根因分类**
我把每个 issue 归到一个 `root_cause_type`（mix_problem / measurement_artifact / channel_routing / budget_allocation）。这个分类决定系统会用什么逻辑链去推理它。如果我分错了，下游的一切都会偏。

**2. action_id 语义**
每个 action 在系统里有一个 ID（比如 `DIAGNOSE_MIX`、`FIX_DENOMINATOR`、`FIX_DESTINATION_ROUTING`）。这个 ID 决定系统给商家显示什么建议，以及如何计算这个建议的价值。如果 ID 的语义和你的意图不符，商家会收到错误的指令。

**3. gmv_lift_prior 的数值**
这是最需要你确认的一个。每个 action 都有一个 `gmv_lift_prior`，这是系统对"这个 action 能带来多少 GMV 提升"的初始估计。我根据你的数据用公式推导了每个值，但公式的选择本身就是一个判断。

比如 WB Case 5（Meta 目的地路由），我的推导是：
```
CAC -17.4% × (2290 新客 × $47 AOV / $150k 月GMV) ≈ 0.12
```
这个 0.12 是否合理？你认为这个 action 对 GMV 的真实影响更高还是更低？

**4. 哪些是通用 pattern，哪些是 WB 专属**
我把 `conversion_subscription_mix` 和 `acquisition_cac_channel_mix` 设计成了可复用的通用 meta-pattern（`reusable: true`）。
意思是系统认为这两个问题不是 WB 独有的，其他品牌也会遇到。
你的判断是：这个假设成立吗？在你接触的其他品牌里，有没有遇到过类似的 subscription mix 或 Meta 投放目的地路由问题？

---

## 第三件事：我的翻译逻辑是什么

方便你判断时有一个统一的参照系。

**三层结构**

你提供的内容最终被组织成三层：

```
Layer 1: Meta-Pattern（通用逻辑模板）
  — 描述：这类问题的诊断逻辑（没有具体数字，只有结构）
  — 你维护：触发条件的结构、分析路径、action 的商业意图

Layer 2: Brand Binding（品牌参数绑定）
  — 描述：这个品牌的具体阈值、实体名称、初始置信度
  — 你提供：原始数字 → 我转化为参数 → 后续由真实数据校准

Layer 3: Use Case（证据原档）
  — 描述：你观察到的原始数据、实际发生的因果链
  — 你写：只存原始数字和叙述，永远不被修改
```

**最重要的原则**：数字不来自我的推断，数字来自你的观察。

如果你给我的是 "CAC 降了很多"，我没法转化。
如果你给我的是 "CAC 从 $54.79 降到 $45.25（-17.4%）"，我可以精确转化，并且留下完整的推导路径供后续校准。

---

## 第四件事：接下来你可以帮到我的地方

你的角色不是"写文档的人"，你是**商业逻辑的校准者和新 issue 的发现者**。

具体来说：

**你能直接判断，我需要你的答案**：
- 上面翻译的 6 个 WB issue，哪个的 `root_cause_type`、`action_id` 或 `gmv_lift_prior` 你看了觉得不对？
- wb_006 里还缺两个值：库存安全天数阈值（你觉得多少天以下算紧张？）、SKU 集中度阈值（占 Meta 预算超过多少 % 触发预警？）
- 你认为 `conversion_subscription_mix` 这个 pattern 在其他品牌也会出现吗？

**你能持续提供的，我会持续翻译**：
- 新品牌的 use case（我们已经建立了翻译工作流，新内容按同样的方式进入系统）
- 现有品牌的校准反馈（某个 action 实际执行了，结果是什么——这是让系统从 `partner_prior` 升级到 `outcome_calibrated` 的必要输入）
- 你认为缺失的 pattern（你接触的 issue 里，有没有我们还没覆盖的根因类型？）

**IP 边界**：
你的原始内容（用词、叙述、数字）永远存在原稿目录里，不被修改，不被 LLM 处理。系统里的 YAML 文件是我对你的内容的"翻译结果"，如果翻译有偏差，以你的原稿为准，我来修正系统。

---

## 行动项（请你在方便的时候反馈）

1. 浏览一下翻译结果（我可以发你几个 YAML 的可读摘要，不需要你看代码）
2. 对上面 4 个翻译判断类别，告诉我哪里不对
3. wb_006 的两个待定阈值，告诉我你的判断值
4. 如果你觉得某个 issue 的商业逻辑我理解有误，直接告诉我，你说的就是正确答案

---

*感谢你到目前为止的内容贡献，这是系统能真正帮到商家的基础。*
