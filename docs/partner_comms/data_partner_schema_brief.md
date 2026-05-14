# Decision Engine V3 — 数据接入需求说明

**文档类型**: 数据对接 Partner 沟通文档
**对象**: 数据接入 Partner
**版本**: v1.0 (2026-04-12)
**作者**: Yubo

---

## 一句话总结

你需要按照下面的字段表，以日级频率推送标准化的商家指标到 V3 接入层（L0）。
V3 的 L0 层会做 schema 验证和归一化，**不需要你在源头做复杂计算**，只需要推送原始指标。

---

## 第一部分：需要哪些字段

### 1.1 Retention 维度（订单行为）

| 字段名 | 类型 | 含义 | 来源系统 | 可为 null？ |
|--------|------|------|---------|------------|
| `overdue_ratio` | float | 当前最高风险客户的逾期比率（实际购买间隔 / 平均补货周期） | 订单系统 | 否（缺失则该维度 fallback 到 WATCH 状态，不是跳过） |
| `repeat_purchase_rate` | float (0–1) | 过去 30 天内有复购行为的客户比例 | 订单系统 | 否 |
| `days_since_last_order_p50` | int | 活跃客户最近一次下单距今天数（p50 分位数） | 订单系统 | 否 |

**备注**: `overdue_ratio` = 最近活跃客户中，实际购买间隔超过预期补货周期的比率。
触发逻辑：≥ 1.2 WATCH → ≥ 1.5 DEGRADING → ≥ 1.8 CRITICAL

---

### 1.2 Acquisition 维度（广告效率）

| 字段名 | 类型 | 含义 | 来源系统 | 可为 null？ |
|--------|------|------|---------|------------|
| `cac_7d` | float (USD) | 过去 7 天平均客户获取成本 | 广告平台 (Meta/Google) | 否 |
| `cac_baseline_30d` | float (USD) | 过去 30 天 CAC 均值（作为基线） | 广告平台 | 否 |
| `roas_7d` | float | 过去 7 天广告投入产出比 | 广告平台 | 否 |
| `roas_baseline_30d` | float | 过去 30 天 ROAS 均值 | 广告平台 | 否 |

**备注**:
- 触发逻辑：`cac_7d > cac_baseline_30d × 1.15` + `roas_7d < roas_baseline_30d × 0.9` → DEGRADING
- `cac_7d > cac_baseline_30d × 1.35` → CRITICAL（单独触发）

---

### 1.3 Conversion 维度（转化漏斗）

| 字段名 | 类型 | 含义 | 来源系统 | 可为 null？ |
|--------|------|------|---------|------------|
| `mobile_atc_rate` | float (0–1) | 移动端加购率（add-to-cart / sessions） | GA4 / 店铺后台 | 否 |
| `desktop_atc_rate` | float (0–1) | 桌面端加购率 | GA4 / 店铺后台 | 否 |
| `mobile_traffic_pct` | float (0–1) | 移动端流量占比 | GA4 | 否 |
| `checkout_cvr` | float 或 dict | 结账转化率 | 订单 + 流量 | 否 |

**关于 `checkout_cvr` 的两种格式**:

```json
// 格式 A（简单，推荐 Day 1）
"checkout_cvr": 0.032

// 格式 B（带趋势，启用后可检测 CRITICAL 状态）
"checkout_cvr": {
  "current": 0.032,
  "3d_ago": 0.041
}
```

建议 Day 1 先推格式 A，等接入稳定后切换格式 B。格式 B 会额外检测下行趋势触发 CRITICAL。

---

### 1.4 Promotion 维度（促销效果）

| 字段名 | 类型 | 含义 | 来源系统 | 可为 null？ |
|--------|------|------|---------|------------|
| `promo_incrementality` | float (0–1) | 促销增量度（促销带来的纯增量订单比例） | 归因系统 / 实验结果 | 否 |
| `existing_customer_promo_pct` | float (0–1) | 领取促销的现有客户比例（非新客） | CRM + 订单 | 否 |
| `promo_margin_delta` | float | 当前促销活动引起的毛利率变化（负数=毛利下降） | 财务/订单系统 | 否 |

**备注**: `promo_incrementality < 0.25` → DEGRADING；`< 0.40` → WATCH

---

### 1.5 商家基础指标（Impact 计算用）

| 字段名 | 类型 | 含义 | 更新频率 |
|--------|------|------|---------|
| `monthly_gmv` | float (USD) | 当月 GMV（滚动 30 天） | 日更 |
| `monthly_ad_spend` | float (USD) | 当月广告支出（滚动 30 天） | 日更 |
| `avg_order_value` | float (USD) | 过去 30 天平均订单金额 | 日更 |
| `monthly_orders` | int | 过去 30 天订单数 | 日更 |
| `avg_margin_pct` | float (0–1) | 平均毛利率 | 日更（或周更） |

---

### 1.6 可选字段（Phase 2 启用）

以下字段 V3 代码已预留位置，Phase 2 会激活。Day 1 不要求，但如果你已经有，欢迎一起推：

| 字段名 | 类型 | 用途 |
|--------|------|------|
| `inventory_days_p10` | float | 库存天数 p10 分位（最紧张的 SKU）→ 库存安全门控 |
| `subscription_rate_pop_delta` | float | 订阅率 WoW 变化（pp）→ 订阅率诊断触发 |
| `top_sku_order_share` | float (0–1) | 最高份额 SKU 的订单占比 → SKU 混合稀释诊断 |
| `shopcash_order_share` | float (0–1) | ShopCash 订单占比 → 分母校正诊断 |

---

## 第二部分：数据频率

| 数据类型 | 推送频率 | 截止时间 | 说明 |
|---------|---------|---------|------|
| 所有日级指标（1.1–1.5 全部字段） | **每日一次** | UTC 06:00 | V3 在 UTC 08:00 前完成 MSM 状态计算 |
| 商家基础指标（1.5） | 每日 | 同上 | 滚动 30 天口径 |
| 可选字段（1.6） | 每日（如有） | 同上 | 缺失不阻断 |

**为什么是日级？**
MSM 状态计算是日批次，状态一旦进入 DEGRADING 或以上会持续触发 decision pipeline。
日级频率足以覆盖 CPG 品牌的决策节奏（不需要实时流）。

---

## 第三部分：谁负责数据质量

**架构原则：接入层（L0）是唯一的 schema 验证边界。**

```
你 (data partner)          L0 Signal Plane             L1 MSM
推送原始指标      →     schema 验证 + 归一化    →     状态计算
                         ↓ 不合格 → 报错并跳过
                         ✓ 合格 → 写入 DB
```

**你需要保证**:
1. 字段名称与上表完全一致（大小写敏感）
2. 类型正确（float 不要传字符串 "0.15"）
3. 必填字段不为 null（null 会导致该维度 fallback 到 **WATCH**，而非 HEALTHY——系统仍会产出候选 action，但依据不足，属于有噪声的决策输出）

**我们（L0）负责**:
1. 范围校验（如 float (0–1) 的字段超出范围 → 截断并 WARNING）
2. 格式兼容（如 `checkout_cvr` 支持 float 或 dict 两种格式）
3. 归一化（字段名 alias 映射，如有历史字段名变更）
4. 异常日志（哪些字段缺失、哪些超出预期范围）

**错误处理优先级**:
- 必填字段缺失 → 该维度 fallback 到 **WATCH**（不是跳过，也不是 HEALTHY——系统会继续产出候选 action，但信号依据不足，属于有噪声的决策输出）
- 类型错误 → L0 记录 ERROR，该条记录整体跳过
- 范围异常 → L0 记录 WARNING，截断后继续处理

---

## 第四部分：推送方式（待对齐）

以下是需要我们一起确认的实现细节，请你反馈：

| 问题 | 你的答复 |
|------|---------|
| 推送协议：REST API / 文件上传 / DB 写入？ | |
| 每次推送：单商家单条 / 批量多商家？ | |
| merchant_id 格式：你们系统的商家唯一标识是什么？ | |
| 历史数据回填：能提供多少天的历史数据？ | |
| 如果某天某个字段没有数据，推送方式（跳过该字段 vs 推 null）？ | |

---

*如有问题，请随时联系 Yubo。*
