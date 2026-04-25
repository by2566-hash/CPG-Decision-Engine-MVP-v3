# Decision Engine V3 — Merchant Dashboard UX/UI Guide

This document explains the design philosophy, interaction logic, and key features of the high-fidelity pure frontend mockup (`mockup/merchant/`). 

> **Disclaimer**: This is a pure UI/UX frontend prototype. It relies on internal mock data (`app.js`) meant exclusively to demonstrate the **interactive steering experience**, **trust-building visualizations**, and **decision flow** of the V3 engine. It does not contain live data pipelines or external active ML models.

---

## 1. Design Philosophy: Trust over Automation
In the CPG B2B software space, merchants distrust "black box" AI. This dashboard is precision-engineered to address this by:
- **Never Auto-Executing:** Every AI generated insight forces the user into a human-in-the-loop approval workflow.
- **Hypothesis vs. Recommendation:** AI outputs explicitly disclose their confidence levels to manage expectations safely.
- **Visible Guardrails:** AI constraints and mathematical bounds are made visible and interactive to the user.

---

## 2. Core Functional Modules

### 🧭 A. Global Navigation & Shadow Mode Badge
- **Dark Mode Aesthetic:** Employs a glass-morphic, high-contrast dark theme (tailored for data-heavy "Bloomberg Terminal" aesthetics).
- **Shadow Mode Indicator:** The top navigation bar prominently displays `Shadow Mode — AI is learning, you control all actions`. This reminds the merchant that the engine is passively logging recommendations without mutating live store configurations autonomously.

### 📊 B. Business Health Monitor (L1: Merchant State Machine)
*Located in the `Business Health` tab.*
- Matches the backend **Layer 1** logic.
- Displays 4 discrete dimensions: **Customer Acquisition, Sales Conversion, Customer Retention, Merchandise Promotion**.
- Progress bars visually represent the state of each dimension (Healthy🟢, Watch🟡, Degrading🟠, Critical🔴) using an exact `urgency_score`.

### 🎛️ C. Strategic Objectives & Policy Steering (L2: Policy Pack)
*Located in the `AI Insights` tab.*
The AI does not decide _what_ your ultimate goal is; you do. This interface links to directly the backend's L2 LinUCB scoring engine.
- **4 Presets:** Merchants can click buttons like *Aggressive Scale* or *Profit Protection* to automatically align the underlying utility weights (`U_base`).
- **⚙️ Custom Mode (Guardrailed Fine-Tuning):** Clicking this unlocks 4 interactive sliders (`Growth LKG`, `Margin LKM`, `Inventory Risk LKI`, `Retention LKR`).
  - **Dynamic Normalization:** Dragging any slider will trigger a real-time mathematical normalization. The system enforces that the sum of all 4 weights is exactly `1.0` (backend mathematical rule).
  - **Safety Boundaries:** The UI implicitly prevents any dimension weight from dropping below a hard red-line of `0.05` to avoid edge-casing the scoring algorithm.

### 💡 D. AI Insights & Cross-Module Suppressions
*Located in the `AI Insights` tab.*
This is where the engine presents ranked action candidates after applying the mathematical filters across layers.
- **Confidence Disclosure:**
  - `Recommendation` (Green ✅): High confidence, rooted in the store's own historical CRM data. 
  - `Hypothesis` (Blue 📊): Low confidence (<60%), relying on CPG industry benchmarks because of cold-start constraints.
- **Dollar Impact Estimation:** Each insight translates abstract operations into clear expected returns: `+$11,192/mo (range $5,596–$20,146)`.
- **🛑 Cross-Module Correlator (Warnings Tab):** A flagship feature demonstrating system intelligence. Instead of silently dropping an action because it causes a conflict (e.g., *increasing ad spend while checkout is broken*), the UI explicitly lists the action as "Dimmed/Grayed Out" with a vivid warning explaining **WHY** the AI suppressed it. 

### 🔻 E. Conversion Funnels (L0/L1 signal — demo)
*Located in the `Conversion Funnels` tab.*
- End-to-end **session → purchase** funnel with deterministic demo counts tied to the same baselines as `MOCK_MERCHANT` (visitors / orders) so the story stays consistent in investor meetings.
- **Primary funnel** pairs a canvas chart with bar strips showing step-over-step drop-off; **Mobile vs desktop** uses grouped bars (blue = mobile, coral = desktop) to dramatize the mobile conversion gap that feeds L1 **Conversion** MSM state.
- **Decision Engine hooks** card links the view to Cross-Module suppression and RFM prioritization (narrative only; no live API).

### 🎯 F. Customer Segmentation — RFM (L0/L1 signal — demo)
*Located in the `Segmentation (RFM)` tab.*
- **RFM quintiles** (Recency × Frequency heatmap) and named segments (**Champions**, **Loyal**, **At Risk**, **New**, etc.) with revenue mix and suggested plays — aligned with retention / promotion dimensions from the README.
- KPI strip (customers in scope, median recency, avg monetary) sets context before the segment table; **Refresh** re-renders the same demo snapshot (simulates cache refresh).
- Explicitly **demo / investor** data — no PII; suitable for VC walkthrough alongside Shadow Mode messaging.

### 📅 G. Action Cards & Weekly Planner (L3: Value Intelligence)
*Located in the `Action Cards` tab.*
- **🌟 Weekly Action Plan Banner:** An aggregated natural-language summary (Narrative) at the top. The UI automatically synthesizes the Top 2 pending actions and states the exact primary modules being targeted this week.
- **Action Lifecycle (Pending → Done):** Simulates the final "Approve" (Merchant Approval Gate) stage, turning theoretical insights into executable deployment tasks. Provides an interactive feedback loop dropdown (e.g., "Met my expectations", "Price wasn't right") mimicking the system's RLHF logging (Layer 5/WSM).

---

## 3. How to Demonstrate in a Client Meeting (Demo Script Flow)

To best showcase the architecture through this mockup, follow this interaction path:

1. **Start at `Overview` or `Business Health`:**
   > *"The AI continuously monitors your backend..."* Point out the precise L1 state metrics (e.g., Conversion is 'Degrading').
2. **Navigate to `AI Insights`:**
   > *"Given the degrading conversion, the system proposes these actions..."* Point out the financial impact range and the "Hypothesis" vs "Recommendation" trust labels.
3. **Showcase the `⚙️ Custom` Steering Sliders:**
   > *"But we never black-box the AI. The merchant decides the primary goal."* Click Custom, drag the `Growth` slider up, and observe the other sliders dynamically lowering to maintain the `sum=1.0` requirement limit seamlessly. 
4. **Showcase Action Suppression (`Warnings` filter):**
   > *"Our AI knows what NOT to do."* Click the Warnings tab and highlight the grayed-out card explicitly suppressed by the Cross-Module Correlator.
5. **Open `Conversion Funnels` then `Segmentation (RFM)`:**
   > *"This is how we turn raw Shopline signals into funnel diagnostics and RFM-backed retention plays — before we auto-execute anything."* Call out mobile vs desktop and the RFM revenue concentration (Champions + Loyal).
6. **Visit `Action Cards`:**
   > *"Finally, everything is rolled up into a human-readable Weekly Plan."* End the demo by pointing to the dynamic banner at the top synthesizing the focus for the week.

---

## 4. Technical File Structure (Mockup)

- **`index.html`**: The static DOM shell. Contains the side-navigation, main view containers, and the HTML structure for the sliders and health bars.
- **`styles.css`**: The CSS framework. Includes all variables mapping to the dark-mode theme, glassmorphic layout, and dynamic transitions (like slider movement).
- **`app.js`**: The mock intelligent engine. 
  - Contains `MOCK_MERCHANT` state and the mock `CANDIDATES` knowledge graph.
  - Controls the Normalization math for the L2 sliders.
  - Dynamically builds and injects the Insight DOM elements.
