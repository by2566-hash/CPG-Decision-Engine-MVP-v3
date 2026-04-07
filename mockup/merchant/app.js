/* ── Brand Intelligence — Merchant Dashboard Logic (Dark Theme + Multi-Page) ──
 *
 * Backend source of truth (READ-ONLY):
 *   config.py, pipeline.py, scoring.py, constraints.py, contracts.py,
 *   impact_calculator.py, merchant_state_machine.py
 *
 * 5 pages: Overview → Health → AI Insights → Action Cards → Competitive Intel
 * All V3 scoring runs internally; merchant sees business language only.
 * ── */

// ═══════════════════════════════════════════════════════════════════
//  V3-aligned internal state (merchant never sees these)
// ═══════════════════════════════════════════════════════════════════

const STATE = {
  dimensions: {
    acquisition:  { state: 'WATCH',     urgency: 0.30 },
    conversion:   { state: 'DEGRADING', urgency: 0.60 },
    retention:    { state: 'CRITICAL',  urgency: 0.90 },
    promotion:    { state: 'HEALTHY',   urgency: 0.00 },
  },
  policyWeights: { gmv_lift: 0.40, margin_lift: 0.30, inventory_risk_reduction: 0.20, retention_lift: 0.10 },
  activePolicyId: 'balanced',
  beta: { b1: 0.65, b2: 0.25, b3: 0.10 },
};

// ═══════════════════════════════════════════════════════════════════
//  V3 scoring internals (hidden from UI)
// ═══════════════════════════════════════════════════════════════════

function clip(x, lo = -1, hi = 1) { return Math.max(lo, Math.min(hi, x)); }

function computeBaseUtility(pred, w) {
  return (w.gmv_lift || 0) * clip((pred.gmv_lift || 0) / 0.30)
       + (w.margin_lift || 0) * clip((pred.margin_lift || 0) / 0.10)
       + (w.inventory_risk_reduction || 0) * clip((pred.inventory_risk_reduction || 0) / 0.20)
       + (w.retention_lift || 0) * clip((pred.retention_lift || 0) / 0.20);
}

function applyUrgencyBoost(uBase, urg) { return urg > 0.8 ? uBase * 1.15 : uBase; }
function computeScore(uBase, uUcb, risk) {
  return STATE.beta.b1 * uBase + STATE.beta.b2 * uUcb - STATE.beta.b3 * risk;
}

// V3 impact_calculator.py INDUSTRY_BENCHMARKS
const CANDIDATES = [
  { id: 'REMINDER_ONLY', module: 'retention',
    name: 'Send Replenishment Reminders',
    desc: 'Reach out to customers who are due for a reorder based on their purchase history — no discounts involved.',
    pred: { retention_lift: 0.08, gmv_lift: 0.04 }, risk: 0 },
  { id: 'REALLOCATE_BUDGET', module: 'acquisition',
    name: 'Optimize Ad Spend Allocation',
    desc: 'Shift budget away from underperforming ad channels and concentrate on those with stronger returns.',
    pred: { gmv_lift: 0.12 }, risk: 0 },
  { id: 'REORDER_SHELF', module: 'conversion',
    name: 'Improve Mobile Shopping Experience',
    desc: 'Reorganize your product display for mobile visitors — where the majority of your traffic comes from.',
    pred: { gmv_lift: 0.10 }, risk: 0 },
];

const MOCK_MERCHANT = {
  monthly_gmv: 111266, monthly_ad_spend: 8000,
  avg_order_value: 96.82, monthly_orders: 1156,
  avg_margin_pct: 0.22, monthly_visitors: 46572, cvr: 0.025,
};

// V3 impact_calculator.py confidence (Phase 1 = 0.30)
const PHASE1_CONFIDENCE = 0.30;

const BENCHMARK_PCTS = {
  REMINDER_ONLY:      { low: 0.03, mid: 0.08, high: 0.12 },
  REALLOCATE_BUDGET:  { low: 0.05, mid: 0.12, high: 0.20 },
  REORDER_SHELF:      { low: 0.05, mid: 0.10, high: 0.18 },
};

// L2 Policy Pack Presets
const POLICIES = {
  balanced: {
    label: 'Balanced Growth',
    weights: { gmv_lift: 0.4, margin_lift: 0.3, inventory_risk_reduction: 0.2, retention_lift: 0.1 }
  },
  aggressive: {
    label: 'Aggressive Scale',
    weights: { gmv_lift: 0.7, margin_lift: 0.1, inventory_risk_reduction: 0.1, retention_lift: 0.1 }
  },
  profit: {
    label: 'Profit Protection',
    weights: { gmv_lift: 0.2, margin_lift: 0.6, inventory_risk_reduction: 0.1, retention_lift: 0.1 }
  },
  inventory: {
    label: 'Inventory Clearance',
    weights: { gmv_lift: 0.3, margin_lift: 0.1, inventory_risk_reduction: 0.5, retention_lift: 0.1 }
  }
};

function getDollarBase(mod) {
  switch (mod) {
    case 'retention':   return MOCK_MERCHANT.monthly_gmv;
    case 'acquisition': return MOCK_MERCHANT.monthly_ad_spend;
    case 'conversion':  return MOCK_MERCHANT.avg_order_value * MOCK_MERCHANT.monthly_orders;
    case 'promotion':   return MOCK_MERCHANT.monthly_gmv * MOCK_MERCHANT.avg_margin_pct;
    default:            return 0;
  }
}

function computeImpact(id, mod) {
  const b = BENCHMARK_PCTS[id];
  if (!b) return { low: 0, mid: 0, high: 0 };
  const base = getDollarBase(mod);
  return { low: Math.round(b.low * base), mid: Math.round(b.mid * base), high: Math.round(b.high * base) };
}

function rankCandidates() {
  return CANDIDATES.map(c => {
    let uBase = computeBaseUtility(c.pred, STATE.policyWeights);
    const urg = STATE.dimensions[c.module] ? STATE.dimensions[c.module].urgency : 0;
    uBase = applyUrgencyBoost(uBase, urg);
    const score = computeScore(uBase, 0, c.risk);
    return { ...c, uBase, score };
  }).sort((a, b) => b.score - a.score);
}

// ═══════════════════════════════════════════════════════════════════
//  Merchant-facing data models
// ═══════════════════════════════════════════════════════════════════

const DIM = {
  acquisition: {
    label: 'Customer Acquisition', icon: '📈',
    signals: [
      { name: '7-Day Acquisition Cost', value: '$24.50' },
      { name: '30-Day Avg. Cost', value: '$18.20' },
      { name: '7-Day Return on Ad Spend', value: '2.8×' },
      { name: '30-Day Avg. ROAS', value: '3.5×' },
    ],
    summaries: {
      HEALTHY: 'Acquisition costs and returns are within healthy ranges.',
      WATCH: 'Acquisition costs are rising slightly — keep an eye on ad spend efficiency.',
      DEGRADING: 'Ad spend returns are declining. Consider reviewing channel allocation.',
      CRITICAL: 'Acquisition costs are critically high. Immediate action recommended.',
    },
  },
  conversion: {
    label: 'Sales Conversion', icon: '🛒',
    signals: [
      { name: 'Mobile Add-to-Cart Rate', value: '3.2%' },
      { name: 'Desktop Add-to-Cart Rate', value: '7.8%' },
      { name: 'Mobile Traffic Share', value: '68%' },
      { name: 'Checkout Conversion', value: '1.9%' },
    ],
    summaries: {
      HEALTHY: 'Conversion rates are strong across all devices.',
      WATCH: 'Slight gap between mobile and desktop conversion.',
      DEGRADING: 'Mobile conversion is significantly lagging desktop. With 68% mobile traffic, this is high impact.',
      CRITICAL: 'Conversion rates are critically low. Checkout flow may need urgent attention.',
    },
  },
  retention: {
    label: 'Customer Retention', icon: '💎',
    signals: [
      { name: 'Overdue Reorder Ratio', value: '1.85×' },
      { name: 'Repeat Purchase Rate', value: '22%' },
      { name: 'Median Days Between Orders', value: '45 days' },
    ],
    summaries: {
      HEALTHY: 'Customer loyalty and repeat purchase patterns are strong.',
      WATCH: 'Some customers are overdue for their next purchase.',
      DEGRADING: 'Repeat purchase rates are declining. Risk of customer churn.',
      CRITICAL: 'A significant number of customers are overdue for reorders. Risk of losing them is high.',
    },
  },
  promotion: {
    label: 'Promotions & Pricing', icon: '🏷️',
    signals: [
      { name: 'Promo Effectiveness', value: '52%' },
      { name: 'Existing Customer Promo Usage', value: '38%' },
      { name: 'Promo Margin Impact', value: '+1.2%' },
    ],
    summaries: {
      HEALTHY: 'Promotions are driving genuine new sales with healthy margins.',
      WATCH: 'Promo effectiveness is slipping slightly.',
      DEGRADING: 'Promotions are showing fatigue. Too many existing customers using promos.',
      CRITICAL: 'Promo ROI is dangerously low. Cannibalizing margin.',
    },
  },
};

// V3 constraints → merchant protections
const PROTECTIONS = [
  'Margin Protection: Your profit margin will never drop below 15%.',
  'Reminders Before Discounts: We always try a friendly reminder first.',
  'Proven Impact Required: Promotions must show at least 30% genuine uplift.',
  'New Visitor Protection: First-time visitors never receive discounts.',
  'Inventory Safety: No discounts when inventory is below 5 days of supply.',
  'Proper Attribution: Each action has an appropriate measurement window.',
];

// Action Cards data — with feedback status tracking (GAP-4)
const ACTIONS_COMPLETED = [
  {
    title: 'Fix the big product-page → add-to-cart leak',
    tag: 'Completed',
    detail: 'Revise top product pages (start with Premium Wireless Headphones, Smart Fitness Tracker, Portable Speaker): add 2–3 high-quality images + 30-sec demo video, short bullet USPs, clear shipping & returns, price transparency, urgency (low-stock badge), one-click buy and mobile-optimized CTA. Implement product badges (best-seller, warranty) and customer reviews snippets above the fold.',
    impact: 'Reducing this drop by half (73% → 36%) could mean ~6,000 incremental add-to-cart events. At a 45% cart-to-order rate (industry-optimized checkout), that could produce ~1,260 extra orders and ~$120K incremental revenue (assuming current AOV ~$97) and unchanged downstream conversion.',
    status: 'done',
    riskLevel: 'LOW',
    feedbackGiven: false,
  },
  {
    title: 'Recover carts between Add-to-Cart and Checkout Initiated with automated flows',
    tag: 'Completed',
    detail: 'Set up an automated abandoned-cart sequence (email + optional SMS): send first reminder within 1 hour, second with social proof within 24 hours, third with a small incentive (free shipping or 5–10% off) at 48–72 hours. Personalize using product/SKU left in cart and include one-click return to checkout and dynamic coupon tokens. Segment by high-value carts (AOV above store average) to offer different incentives.',
    impact: 'Recovering 15–20% back into checkout-initiated, and converting at historical checkout conversion rate, yields ~150 additional orders per month at current AOV (~$97). Even a conservative 5% recovery yields ~50 extra orders.',
    status: 'done',
    riskLevel: 'LOW',
    feedbackGiven: true,
    feedbackType: 'executed_met_expectations',
  },
  {
    title: 'Shift ad spend from low-ROI Social to Email growth & high-ROI channels',
    tag: 'Completed',
    detail: 'Reduce paid social spend and reallocate ~20–30% of that budget to: (1) email list growth campaigns (lead magnets & welcome flows), (2) paid retargeting/dynamic ads for cart abandoners. Also enable UTM tracking for channel-level LTV measurement.',
    impact: 'Track incremental revenue and ROI of shifts.',
    status: 'done',
    riskLevel: 'HIGH',
    feedbackGiven: false,
  },
  {
    title: 'Scale Email & Direct — reallocate from underperforming Social',
    tag: 'Completed',
    detail: 'Email: visitors 1,464, conversion 5.9%, ROI 6.2 (best performer). Direct visitors 1,856, conversion 4.08% (likely loyal/returning customers). Social: visitors 5,800, conversion 1.8%, ROI 1.18 (weakest). Takeaway: prioritize scaling email campaigns (segmented product promos, cart recovery, browse abandonment) and monetize direct traffic via VIP offers.',
    impact: 'Reallocate a portion of social ad budget into email list growth (lead magnets on social, gated discount in exchange for email and high-intent Paid Search keywords where ROI is acceptable).',
    status: 'done',
    riskLevel: 'LOW',
    feedbackGiven: false,
  },
];

const ACTIONS_PENDING = [];

// V3 feedback_collector.py: 6 valid feedback types
const FEEDBACK_TYPES = [
  { id: 'executed_met_expectations', icon: '✅', label: 'Met my expectations' },
  { id: 'executed_below_expectations', icon: '😕', label: 'Below expectations' },
  { id: 'not_executed_price_too_low', icon: '💰', label: 'Price/discount wasn\'t right' },
  { id: 'not_executed_wrong_timing', icon: '⏰', label: 'Wrong timing' },
  { id: 'not_executed_other_plan', icon: '📋', label: 'Had a different plan' },
  { id: 'partial_executed', icon: '⚡', label: 'Partially executed' },
];

let currentFeedbackAction = null;

// Generate AI insights from V3 candidates
function buildInsights() {
  const ranked = rankCandidates();
  const insights = [];

  // High priority — from CRITICAL dimensions
  Object.entries(STATE.dimensions).forEach(([dim, d]) => {
    const meta = DIM[dim];
    if (d.state === 'CRITICAL') {
      insights.push({
        title: `Major drop at ${meta.label} — Immediate attention needed`,
        body: meta.summaries[d.state] + ` Key signals: ${meta.signals.map(s => s.name + ': ' + s.value).join(', ')}.`,
        priority: 'high',
        category: 'high',
        impact: ranked.find(c => c.module === dim),
      });
    }
  });

  // Opportunities — from DEGRADING
  Object.entries(STATE.dimensions).forEach(([dim, d]) => {
    const meta = DIM[dim];
    if (d.state === 'DEGRADING') {
      insights.push({
        title: `${meta.label} showing decline — opportunity to act`,
        body: meta.summaries[d.state] + ` We recommend addressing this before it becomes critical.`,
        priority: 'medium',
        category: 'opportunity',
        impact: ranked.find(c => c.module === dim),
      });
    }
  });

  // Warnings — from WATCH
  Object.entries(STATE.dimensions).forEach(([dim, d]) => {
    const meta = DIM[dim];
    if (d.state === 'WATCH') {
      insights.push({
        title: `${meta.label} — early warning signal`,
        body: meta.summaries[d.state] + ` No action required yet, but monitoring recommended.`,
        priority: 'low',
        category: 'warning',
        impact: ranked.find(c => c.module === dim),
      });
    }
  });

  // Add the top recommendation as an insight with counterfactual (GAP-3)
  const winner = ranked[0];
  const runnerUp = ranked.length > 1 ? ranked[1] : null;
  const winImpact = computeImpact(winner.id, winner.module);
  const runnerImpact = runnerUp ? computeImpact(runnerUp.id, runnerUp.module) : null;

  insights.push({
    title: `Top recommendation: ${winner.name}`,
    body: winner.desc + ` Expected monthly impact: $${winImpact.mid.toLocaleString()}.`,
    priority: 'high',
    category: 'high',
    impact: winner,
    isTopPick: true,
    counterfactual: runnerUp ? {
      runnerUpName: runnerUp.name,
      runnerUpAction: runnerUp.id,
      runnerUpEstimate: runnerImpact ? runnerImpact.mid : 0,
      topEstimate: winImpact.mid,
      whyNot: `${runnerUp.id} estimated $${(runnerImpact ? runnerImpact.mid : 0).toLocaleString()} vs $${winImpact.mid.toLocaleString()} for ${winner.id}`,
    } : null,
  });

  // Cross-Module Correlator Suppressed Action
  insights.push({
    id: 'suppressed_1',
    category: 'warning',
    dim: 'acquisition',
    title: 'Increase Ad Budget on Google Ads',
    suppressed: true,
    suppressionReason: 'CAC is rising while Conversion is degrading. The engine recommends fixing the conversion leak first before adding top-of-funnel spend.'
  });

  return insights;
}

// ═══════════════════════════════════════════════════════════════════
//  Navigation
// ═══════════════════════════════════════════════════════════════════

function navigateTo(pageId) {
  // Hide all pages, show selected
  document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
  document.getElementById('page-' + pageId).classList.add('active');
  // Update nav items
  document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
  document.querySelector(`.nav-item[data-page="${pageId}"]`).classList.add('active');
  window.scrollTo(0, 0);
}

// ═══════════════════════════════════════════════════════════════════
//  Render: Overview Page
// ═══════════════════════════════════════════════════════════════════

function renderOverview() {
  // KPIs
  const kpis = [
    { label: 'TOTAL REVENUE', value: `$${MOCK_MERCHANT.monthly_gmv.toLocaleString()}`, change: '+8.2% vs prior period', up: true },
    { label: 'TOTAL ORDERS', value: MOCK_MERCHANT.monthly_orders.toLocaleString(), change: '+5.1% vs prior period', up: true },
    { label: 'TOTAL VISITORS', value: MOCK_MERCHANT.monthly_visitors.toLocaleString(), change: '+1.8% vs prior period', up: true },
    { label: 'CONVERSION RATE', value: (MOCK_MERCHANT.cvr * 100).toFixed(1) + '%', change: '-0.3% vs prior period', up: false },
  ];

  const grid = document.getElementById('kpi-grid');
  grid.innerHTML = kpis.map(k => `
    <div class="kpi-card">
      <div class="kpi-label">${k.label}</div>
      <div class="kpi-value">${k.value}</div>
      <div class="kpi-change ${k.up ? 'up' : 'down'}">
        ${k.up ? '↑' : '↓'} ${k.change}
      </div>
    </div>`).join('');

  // Revenue chart (simple canvas line)
  drawRevenueChart();
  drawTrafficChart();

  // Quick insights
  const insights = buildInsights();
  const list = document.getElementById('quick-insights-list');
  list.innerHTML = insights.slice(0, 4).map(i => `
    <div class="quick-insight-item">
      <div class="qi-dot ${i.priority}"></div>
      <div class="qi-text"><strong>${i.title}</strong></div>
    </div>`).join('');

  // Learning Progress (UX-1)
  renderLearningProgress();
}

function drawRevenueChart() {
  const canvas = document.getElementById('revenue-chart');
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  const W = canvas.parentElement.clientWidth - 48;
  const H = 180;
  canvas.width = W; canvas.height = H;

  // Deterministic data
  const data = [62,68,55,72,80,75,88,82,95,90,78,85,92,88,100,105,98,110,95,102,115,108,120,118,125,112,130,128,135,111];

  const max = Math.max(...data);
  const min = Math.min(...data);
  const rangeY = max - min || 1;
  const stepX = W / (data.length - 1);

  // Grid lines
  ctx.strokeStyle = '#1c1c1c';
  ctx.lineWidth = 1;
  for (let i = 0; i < 4; i++) {
    const y = (H / 4) * i + 10;
    ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(W, y); ctx.stroke();
  }

  // Line
  ctx.beginPath();
  ctx.strokeStyle = '#3b82f6';
  ctx.lineWidth = 2;
  data.forEach((v, i) => {
    const x = i * stepX;
    const y = H - 20 - ((v - min) / rangeY) * (H - 40);
    i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
  });
  ctx.stroke();

  // Gradient fill
  const last = data.length - 1;
  ctx.lineTo(last * stepX, H);
  ctx.lineTo(0, H);
  ctx.closePath();
  const grad = ctx.createLinearGradient(0, 0, 0, H);
  grad.addColorStop(0, 'rgba(59,130,246,0.15)');
  grad.addColorStop(1, 'rgba(59,130,246,0)');
  ctx.fillStyle = grad;
  ctx.fill();
}

function drawTrafficChart() {
  const canvas = document.getElementById('traffic-chart');
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  const W = canvas.parentElement.clientWidth - 48;
  const H = 180;
  canvas.width = W; canvas.height = H;

  const categories = ['Direct', 'Organic', 'Paid', 'Social', 'Email', 'Referral'];
  const direct = [820, 900, 1100, 1200, 1500, 1856];
  const paid = [600, 750, 800, 950, 1000, 1200];
  const barW = (W / categories.length) * 0.7;
  const gap = (W / categories.length) * 0.3;
  const max = Math.max(...direct, ...paid);

  categories.forEach((_, i) => {
    const x = i * (barW + gap) + gap / 2;
    // Direct bar
    const h1 = (direct[i] / max) * (H - 30);
    ctx.fillStyle = '#3b82f6';
    ctx.fillRect(x, H - 20 - h1, barW * 0.45, h1);
    // Paid bar
    const h2 = (paid[i] / max) * (H - 30);
    ctx.fillStyle = 'rgba(59,130,246,0.4)';
    ctx.fillRect(x + barW * 0.5, H - 20 - h2, barW * 0.45, h2);
  });

  // Labels
  ctx.fillStyle = '#666';
  ctx.font = '10px Inter, sans-serif';
  ctx.textAlign = 'center';
  categories.forEach((cat, i) => {
    const x = i * (barW + gap) + gap / 2 + barW / 2;
    ctx.fillText(cat, x, H - 4);
  });
}

// ═══════════════════════════════════════════════════════════════════
//  Render: Business Health Page
// ═══════════════════════════════════════════════════════════════════

function renderHealth() {
  // Alert
  const alert = document.getElementById('health-alert');
  const critDims = Object.entries(STATE.dimensions).filter(([_, d]) => d.state === 'CRITICAL');
  if (critDims.length > 0) {
    const [dimKey] = critDims[0];
    const meta = DIM[dimKey];
    alert.className = 'alert-bar critical';
    alert.innerHTML = `
      <span class="alert-bar-icon">⚠️</span>
      <span class="alert-bar-text"><strong>Attention Required — ${meta.label}.</strong> ${meta.summaries.CRITICAL}</span>
      <button class="alert-bar-btn" onclick="navigateTo('insights')">View Insights →</button>`;
  } else {
    alert.className = 'alert-bar hidden';
  }

  // Cards
  const grid = document.getElementById('health-grid');
  grid.innerHTML = '';

  const statusLabel = { HEALTHY: 'Healthy', WATCH: 'Watch', DEGRADING: 'Declining', CRITICAL: 'Critical' };
  const statusClass = { HEALTHY: 'healthy', WATCH: 'watch', DEGRADING: 'declining', CRITICAL: 'critical' };
  const progressColor = { HEALTHY: '#22c55e', WATCH: '#eab308', DEGRADING: '#f97316', CRITICAL: '#ef4444' };

  for (const [dim, meta] of Object.entries(DIM)) {
    const d = STATE.dimensions[dim];
    const sc = statusClass[d.state];
    const signals = meta.signals.map(s =>
      `<div class="health-signal-row"><span class="health-signal-name">${s.name}</span><span class="health-signal-val">${s.value}</span></div>`
    ).join('');

    const urgPct = Math.round(d.urgency * 100);

    grid.innerHTML += `
      <div class="health-card">
        <div class="health-card-top">
          <span class="health-dim-title">${meta.icon} ${meta.label}</span>
          <span class="health-status-pill ${sc}">${statusLabel[d.state]}</span>
        </div>
        <div class="health-summary">${meta.summaries[d.state]}</div>
        <div class="health-signals">${signals}</div>
        <div class="health-progress-wrap">
          <div class="health-progress-label">
            <span>Urgency Level</span>
            <span>${urgPct}%</span>
          </div>
          <div class="health-progress-bar">
            <div class="health-progress-fill" style="width:${urgPct}%;background:${progressColor[d.state]}"></div>
          </div>
        </div>
      </div>`;
  }
}

// ═══════════════════════════════════════════════════════════════════
//  L2 Policy Pack (Strategy Steering)
// ═══════════════════════════════════════════════════════════════════

function initPolicyPack() {
  const container = document.getElementById('policy-presets');
  if (!container) return;

  const buttonsHtml = Object.entries(POLICIES).map(([id, p]) => `
    <button class="policy-btn ${id === STATE.activePolicyId ? 'active' : ''}" id="btn-${id}"
            onclick="changePolicy('${id}')">
      ${p.label}
    </button>
  `).join('');
  
  const customHtml = `
    <button class="policy-btn ${STATE.activePolicyId === 'custom' ? 'active' : ''}" id="btn-custom"
            onclick="activateCustomPolicy()">
      ⚙️ Custom
    </button>`;

  container.innerHTML = buttonsHtml + customHtml;
  updatePolicyEqualizers();
}

function changePolicy(policyId) {
  STATE.activePolicyId = policyId;
  STATE.policyWeights = { ...POLICIES[policyId].weights };

  // Update UI buttons
  const container = document.getElementById('policy-presets');
  if (container) {
    container.querySelectorAll('.policy-btn').forEach(btn => {
      btn.classList.toggle('active', btn.id === `btn-${policyId}`);
    });
  }

  updatePolicyEqualizers();
  
  // Re-run the V3 pipeline (re-rank and render)
  showToast(`Active policy changed to: ${POLICIES[policyId].label}`);
  renderInsights();
}

function activateCustomPolicy() {
  STATE.activePolicyId = 'custom';
  
  const container = document.getElementById('policy-presets');
  if (container) {
    container.querySelectorAll('.policy-btn').forEach(btn => {
      btn.classList.toggle('active', btn.id === 'btn-custom');
    });
  }

  updatePolicyEqualizers();
  showToast(`Custom mode activated. Drag sliders to adjust objectives.`);
}

function updatePolicyEqualizers() {
  const mapping = {
    'lkg': STATE.policyWeights.gmv_lift,
    'lkm': STATE.policyWeights.margin_lift,
    'lki': STATE.policyWeights.inventory_risk_reduction,
    'lkr': STATE.policyWeights.retention_lift
  };

  const isCustom = STATE.activePolicyId === 'custom';

  for (const [key, val] of Object.entries(mapping)) {
    const valEl = document.getElementById(`eq-val-${key}`);
    const sliderEl = document.getElementById(`eq-fill-${key}`);
    if (valEl && sliderEl) {
      valEl.textContent = val.toFixed(2);
      sliderEl.value = Math.round(val * 100);
      sliderEl.disabled = !isCustom;
    }
  }
}

function getRawSliderValues() {
  return {
    lkg: parseInt(document.getElementById('eq-fill-lkg').value, 10),
    lkm: parseInt(document.getElementById('eq-fill-lkm').value, 10),
    lki: parseInt(document.getElementById('eq-fill-lki').value, 10),
    lkr: parseInt(document.getElementById('eq-fill-lkr').value, 10)
  };
}

function normalizeSliderValues(raw) {
  let sum = raw.lkg + raw.lkm + raw.lki + raw.lkr;
  if (sum === 0) return { lkg: 0.25, lkm: 0.25, lki: 0.25, lkr: 0.25 };
  
  let norm = { lkg: raw.lkg/sum, lkm: raw.lkm/sum, lki: raw.lki/sum, lkr: raw.lkr/sum };
  
  // Safety guardrail: Ensure no weight falls below 0.05
  let sum2 = 0;
  for (let k in norm) {
    if (norm[k] < 0.05) norm[k] = 0.05;
    sum2 += norm[k];
  }
  // Re-normalize if limits were hit
  for (let k in norm) norm[k] = norm[k] / sum2;

  return norm;
}

// Fired continuously on dragging slider
function handleSliderDrag() {
  if (STATE.activePolicyId !== 'custom') return;
  const norm = normalizeSliderValues(getRawSliderValues());
  document.getElementById('eq-val-lkg').textContent = norm.lkg.toFixed(2);
  document.getElementById('eq-val-lkm').textContent = norm.lkm.toFixed(2);
  document.getElementById('eq-val-lki').textContent = norm.lki.toFixed(2);
  document.getElementById('eq-val-lkr').textContent = norm.lkr.toFixed(2);
}

// Fired upon releasing slider
function handleSliderDrop() {
  if (STATE.activePolicyId !== 'custom') return;
  const norm = normalizeSliderValues(getRawSliderValues());
  
  STATE.policyWeights = {
    gmv_lift: norm.lkg,
    margin_lift: norm.lkm,
    inventory_risk_reduction: norm.lki,
    retention_lift: norm.lkr
  };
  
  // Snap physical sliders back to exact normalized percentages
  document.getElementById('eq-fill-lkg').value = Math.round(norm.lkg * 100);
  document.getElementById('eq-fill-lkm').value = Math.round(norm.lkm * 100);
  document.getElementById('eq-fill-lki').value = Math.round(norm.lki * 100);
  document.getElementById('eq-fill-lkr').value = Math.round(norm.lkr * 100);
  
  showToast('Custom policy applied. Re-ranking insights...');
  renderInsights();
}

// ═══════════════════════════════════════════════════════════════════
//  Render: AI Insights Page
// ═══════════════════════════════════════════════════════════════════

let allInsights = [];

function renderInsights() {
  allInsights = buildInsights();
  filterInsights('all');
}

function filterInsights(filter) {
  // Tabs
  document.querySelectorAll('#insight-tabs .tab').forEach(t => t.classList.remove('active'));
  document.querySelector(`#insight-tabs .tab[data-filter="${filter}"]`).classList.add('active');

  const filtered = filter === 'all' ? allInsights : allInsights.filter(i => i.category === filter);
  const grid = document.getElementById('insights-grid');

  if (filtered.length === 0) {
    grid.innerHTML = `
      <div style="grid-column:1/-1;text-align:center;padding:60px 0;color:#444">
        <div style="font-size:32px;margin-bottom:8px">✨</div>
        <div>No insights available yet.</div>
        <button class="btn-accent" style="margin-top:16px" onclick="renderInsights()">Generate Insights</button>
      </div>`;
    return;
  }

  grid.innerHTML = filtered.map(i => {
    if (i.suppressed) {
      return `
        <div class="insight-card suppressed">
          <div class="insight-card-top">
            <div class="insight-card-title">${i.title}</div>
            <span class="insight-dim-tag" style="background:#444">${i.dim.toUpperCase()}</span>
          </div>
          <div class="suppression-alert">
            <span style="font-size:14px">🛑</span>
            <div>
              <strong>Action Suppressed by Cross-Module Correlator</strong><br>
              ${i.suppressionReason}
            </div>
          </div>
        </div>`;
    }

    const imp = i.impact ? computeImpact(i.impact.id, i.impact.module) : null;
    // GAP-1: Classification badge (Phase 1 = all HYPOTHESIS)
    const classification = PHASE1_CONFIDENCE >= 0.60 ? 'recommendation' : 'hypothesis';
    const classLabel = classification === 'hypothesis'
      ? '📊 Hypothesis — based on industry benchmarks'
      : '✅ Recommendation — based on your store data';
    // GAP-3: Counterfactual
    const cfHtml = i.counterfactual ? `
      <div class="counterfactual-section">
        <div class="counterfactual-toggle" onclick="this.nextElementSibling.classList.toggle('open')">
          💡 Why this over ${i.counterfactual.runnerUpName}? ▾
        </div>
        <div class="counterfactual-body">
          Alternative considered: <strong>${i.counterfactual.runnerUpName}</strong><br>
          ${i.counterfactual.whyNot}
        </div>
      </div>` : '';
    return `
      <div class="insight-card">
        <div class="insight-card-top">
          <div class="insight-card-title">${i.title}</div>
          <span class="priority-badge ${i.priority}">${i.priority}</span>
        </div>
        <div class="insight-card-body">${i.body}</div>
        ${cfHtml}
        <div class="classification-badge ${classification}">${classLabel}</div>
        <div class="insight-card-footer">
          ${imp ? `
            <div class="impact-range">
              <span class="impact-expected">+$${imp.mid.toLocaleString()}/mo</span>
              <span class="impact-bounds"> (range $${imp.low.toLocaleString()}–$${imp.high.toLocaleString()})</span>
              <div class="confidence-bar-wrap">
                <div class="confidence-bar"><div class="confidence-bar-fill" style="width:${PHASE1_CONFIDENCE * 100}%"></div></div>
                <span class="confidence-label">confidence ${Math.round(PHASE1_CONFIDENCE * 100)}%</span>
              </div>
            </div>` : '<span></span>'}
          <button class="btn-outline" onclick="navigateTo('actions')">View Action →</button>
        </div>
      </div>`;
  }).join('');
}

// ═══════════════════════════════════════════════════════════════════
//  Render: Action Cards Page
// ═══════════════════════════════════════════════════════════════════

function renderActions() {
  // Weekly Planner Narrative
  const plannerBanner = document.getElementById('weekly-planner-narrative');
  const plannerTop = rankCandidates().slice(0, 2);
  
  if (plannerTop.length > 0) {
    const topActions = plannerTop.map(a => a.name).join(', ');
    const modules = [...new Set(plannerTop.map(a => a.module))].join(', ');
    plannerBanner.innerHTML = `🌟 <strong>Weekly Action Plan:</strong> This week, focus on: ${topActions}. <br><strong>Modules targeted:</strong> ${modules}.`;
    plannerBanner.style.display = 'block';
  } else {
    plannerBanner.style.display = 'none';
  }

  // Pending
  const pendingList = document.getElementById('pending-actions');
  document.getElementById('pending-label').textContent = `Pending Actions (${ACTIONS_PENDING.length})`;

  if (ACTIONS_PENDING.length === 0) {
    pendingList.innerHTML = `
      <div class="action-empty">
        <span class="action-empty-icon">💤</span>
        No pending actions at the moment.<br>Check back later for AI-generated recommendations.
      </div>`;
  } else {
    pendingList.innerHTML = ACTIONS_PENDING.map(a => buildActionCard(a)).join('');
  }

  // Completed
  const completedList = document.getElementById('completed-actions');
  document.getElementById('completed-label').textContent = `Completed Actions (${ACTIONS_COMPLETED.length})`;
  completedList.innerHTML = ACTIONS_COMPLETED.map((a, i) => buildActionCard(a, i)).join('');
}

function buildActionCard(a, idx) {
  const tagClass = a.status === 'done' ? 'completed' : 'pending';
  // GAP-1: Classification badge
  const classification = PHASE1_CONFIDENCE >= 0.60 ? 'recommendation' : 'hypothesis';
  const classLabel = classification === 'hypothesis'
    ? '📊 Hypothesis — based on industry benchmarks'
    : '✅ Recommendation — based on your store data';
  // GAP-4c: Risk level badge
  const riskBadge = a.riskLevel === 'HIGH'
    ? '<span class="risk-badge high-risk">⚠️ High Risk</span>'
    : '<span class="risk-badge low-risk">Low Risk</span>';
  // GAP-4b: Feedback button for completed actions
  const feedbackBtn = a.status === 'done'
    ? (a.feedbackGiven
      ? `<span class="btn-done" style="font-size:11px">✓ Feedback: ${FEEDBACK_TYPES.find(f => f.id === a.feedbackType)?.label || 'Submitted'}</span>`
      : `<button class="feedback-trigger" onclick="openFeedbackModal(${idx})">📝 How did this go?</button>`)
    : '';

  return `
    <div class="action-card">
      <div class="action-card-header" onclick="toggleActionCard(this)">
        <span class="action-card-title">${a.title}</span>
        ${riskBadge}
        <span class="action-tag ${tagClass}">${a.tag}</span>
        <span class="action-card-toggle">▼</span>
      </div>
      <div class="action-card-body">
        <div class="classification-badge ${classification}">${classLabel}</div>
        <div class="action-detail-text" style="margin-top:12px">${a.detail}</div>
        ${a.impact ? `<div class="action-detail-text" style="color:#999;border-top:1px solid #222;padding-top:12px"><strong style="color:#22c55e">Expected Impact:</strong> ${a.impact}</div>` : ''}
        <div class="action-card-buttons">
          ${a.status === 'done'
            ? `<button class="btn-done">✓ Done</button>${feedbackBtn}`
            : '<button class="btn-accent" onclick="approveAction(this)">Approve</button><button class="btn-outline">Dismiss</button>'
          }
        </div>
        ${a.status === 'done' ? '<div class="rollback-msg"><span class="rollback-icon">🔄</span> Rollback was available for 48 hours after execution</div>' : ''}
      </div>
    </div>`;
}

function toggleActionCard(header) {
  const body = header.nextElementSibling;
  body.classList.toggle('open');
  const toggle = header.querySelector('.action-card-toggle');
  toggle.textContent = body.classList.contains('open') ? '▲' : '▼';
}

function approveAction(btn) {
  // GAP-4a: Show rollback window in toast
  showToast('✓ Action approved — you can undo this within 48 hours.');
  btn.textContent = '✓ Approved';
  btn.disabled = true;
  btn.className = 'btn-done';
  // Add rollback message below
  const cardBody = btn.closest('.action-card-body');
  const existingRollback = cardBody.querySelector('.rollback-msg');
  if (!existingRollback) {
    const msg = document.createElement('div');
    msg.className = 'rollback-msg';
    msg.innerHTML = '<span class="rollback-icon">🔄</span> You can undo this action within 48 hours';
    cardBody.appendChild(msg);
  }
}

// ═══════════════════════════════════════════════════════════════════
//  Render: Competitive Intel Page
// ═══════════════════════════════════════════════════════════════════

function renderCompetitive() {
  // Market Position
  document.getElementById('market-position').innerHTML = `
    <div class="comp-section-title">📍 Market Position</div>
    <div class="comp-text">
      This store sits as a healthy mid-market electronics/gadgets retailer; monthly revenue and order volume are solid for an independent brand, and on-site conversion appears at or slightly above category average. However, average order value trails top performers and there is visible upside in revenue scaling and margin expansion through product mix, upsell, and retention improvements.
    </div>`;

  // Industry Benchmarks
  document.getElementById('industry-benchmarks').innerHTML = `
    <div class="comp-section-title">📊 Industry Benchmarks</div>
    <p class="comp-text" style="margin-bottom:16px">How you compare to the market:</p>
    <div class="benchmark-grid">
      <div class="benchmark-item">
        <div class="benchmark-label">Conversion Rate</div>
        <div class="benchmark-value">2.50%</div>
        <div class="benchmark-compare">Top Performer: 5.00%</div>
      </div>
      <div class="benchmark-item">
        <div class="benchmark-label">Average Order Value</div>
        <div class="benchmark-value">$${MOCK_MERCHANT.avg_order_value.toFixed(2)}</div>
        <div class="benchmark-compare">Top Performer: $200.00</div>
      </div>
      <div class="benchmark-item">
        <div class="benchmark-label">Industry Growth</div>
        <div class="benchmark-value">~8.0%</div>
        <div class="benchmark-compare">Avg Revenue: $75K/mo</div>
      </div>
    </div>`;

  // Strengths
  document.getElementById('strengths-card').innerHTML = `
    <div class="comp-section-title">💪 Your Strengths</div>
    <p class="comp-text" style="margin-bottom:12px">What you're doing well:</p>
    <div class="comp-list-item">
      <div>
        <div class="comp-list-title">Solid Order Volume and Revenue</div>
        <div class="comp-list-text">1,156 monthly orders and ~$111K monthly revenue indicates a business with repeatable demand and operational capability beyond early-stage experimentation.</div>
      </div>
    </div>
    <div class="comp-list-item">
      <div>
        <div class="comp-list-title">Above-Average Conversion Rate</div>
        <div class="comp-list-text">At 2.5%, you're outperforming many independent electronics e-commerce sites — a sign of strong UX, relevant traffic, and effective product-market fit.</div>
      </div>
    </div>`;

  // Opportunities
  document.getElementById('opportunities-card').innerHTML = `
    <div class="comp-section-title">🌱 Growth Opportunities</div>
    <p class="comp-text" style="margin-bottom:12px">Untapped potential:</p>
    <div class="comp-list-item">
      <div>
        <div class="comp-list-header">
          <span class="comp-list-title">Expand into Premium & Higher-Margin SKUs</span>
          <span class="comp-verdict negative">Negative</span>
        </div>
        <div class="comp-list-text">Introduce premium product tiers and exclusive bundles to capture higher AOVs and margins. Use targeted campaigns to re-frame brand perception.</div>
      </div>
    </div>
    <div class="comp-list-item">
      <div>
        <div class="comp-list-header">
          <span class="comp-list-title">Build Customer Retention Engine</span>
          <span class="comp-verdict negative">Negative</span>
        </div>
        <div class="comp-list-text">Drive repeat purchases via email flows, subscriptions, and loyalty programs. Current repeat rate of 22% has significant room for improvement.</div>
      </div>
    </div>`;
}

// ═══════════════════════════════════════════════════════════════════
//  Utilities
// ═══════════════════════════════════════════════════════════════════

function showToast(msg) {
  const t = document.getElementById('toast');
  t.textContent = msg;
  t.classList.add('show');
  setTimeout(() => t.classList.remove('show'), 3000);
}

// ═══════════════════════════════════════════════════════════════════
//  UX-1: Learning Progress
// ═══════════════════════════════════════════════════════════════════

function renderLearningProgress() {
  const el = document.getElementById('learning-progress');
  if (!el) return;

  // V3 Phase 1 metrics
  const dataPoints = 4; // ACTIONS_COMPLETED.length
  const confidenceNow = PHASE1_CONFIDENCE; // 0.30
  const confidenceTarget = 0.60; // contracts.py threshold for RECOMMENDATION
  const progressPct = Math.round((confidenceNow / confidenceTarget) * 100);
  const feedbackCount = ACTIONS_COMPLETED.filter(a => a.feedbackGiven).length;

  el.innerHTML = `
    <div class="learning-grid">
      <div class="learning-item">
        <div class="learning-item-header">
          <span class="learning-item-title">Model Confidence</span>
          <span class="learning-phase-badge">Phase 1</span>
        </div>
        <div class="learning-item-value">${Math.round(confidenceNow * 100)}%</div>
        <div class="learning-item-desc">
          Target: ${Math.round(confidenceTarget * 100)}% for auto-recommendations.
          Currently using industry benchmarks.
        </div>
        <div class="learning-bar">
          <div class="learning-bar-fill" style="width:${progressPct}%;background:#3b82f6"></div>
        </div>
      </div>
      <div class="learning-item">
        <div class="learning-item-header">
          <span class="learning-item-title">Actions Taken</span>
        </div>
        <div class="learning-item-value">${dataPoints}</div>
        <div class="learning-item-desc">
          Need ~30 data points to reach full confidence.
          Each action you complete helps the AI learn.
        </div>
        <div class="learning-bar">
          <div class="learning-bar-fill" style="width:${Math.round((dataPoints / 30) * 100)}%;background:var(--green)"></div>
        </div>
      </div>
      <div class="learning-item">
        <div class="learning-item-header">
          <span class="learning-item-title">Feedback Given</span>
        </div>
        <div class="learning-item-value">${feedbackCount} / ${dataPoints}</div>
        <div class="learning-item-desc">
          Your feedback directly improves recommendation quality.
          Rate completed actions to accelerate learning.
        </div>
        <div class="learning-bar">
          <div class="learning-bar-fill" style="width:${dataPoints > 0 ? Math.round((feedbackCount / dataPoints) * 100) : 0}%;background:var(--yellow)"></div>
        </div>
      </div>
    </div>`;
}

// ═══════════════════════════════════════════════════════════════════
//  GAP-4b: Feedback Modal
// ═══════════════════════════════════════════════════════════════════

function openFeedbackModal(actionIndex) {
  currentFeedbackAction = actionIndex;
  const action = ACTIONS_COMPLETED[actionIndex];
  const modal = document.getElementById('feedback-modal');
  document.getElementById('feedback-action-title').textContent = action.title;

  const optionsEl = document.getElementById('feedback-options');
  optionsEl.innerHTML = FEEDBACK_TYPES.map(ft => `
    <label class="feedback-option" onclick="selectFeedback(this, '${ft.id}')">
      <input type="radio" name="feedback" value="${ft.id}">
      <span class="fb-icon">${ft.icon}</span>
      <span class="fb-label">${ft.label}</span>
    </label>`).join('');

  document.getElementById('feedback-note').value = '';
  modal.classList.add('show');
}

function selectFeedback(el, typeId) {
  document.querySelectorAll('.feedback-option').forEach(o => o.classList.remove('selected'));
  el.classList.add('selected');
  el.querySelector('input').checked = true;
}

function closeFeedbackModal(event) {
  if (event && event.target !== event.currentTarget) return;
  document.getElementById('feedback-modal').classList.remove('show');
  currentFeedbackAction = null;
}

function submitFeedback() {
  const selected = document.querySelector('.feedback-option.selected input');
  if (!selected) { showToast('Please select a feedback option.'); return; }

  const action = ACTIONS_COMPLETED[currentFeedbackAction];
  action.feedbackGiven = true;
  action.feedbackType = selected.value;

  closeFeedbackModal();
  showToast('✓ Feedback recorded — this helps the AI learn!');
  renderActions(); // re-render to update button state
  renderLearningProgress(); // update learning metrics
}

// ═══════════════════════════════════════════════════════════════════
//  UX-2: Notification Dropdown
// ═══════════════════════════════════════════════════════════════════

function toggleNotifications() {
  const dropdown = document.getElementById('notif-dropdown');
  dropdown.classList.toggle('show');

  // Populate alerts on first open
  const list = document.getElementById('notif-list');
  if (list.childElementCount === 0) {
    const alerts = [];

    Object.entries(STATE.dimensions).forEach(([dim, d]) => {
      const meta = DIM[dim];
      if (d.state === 'CRITICAL') {
        alerts.push({
          level: 'critical',
          text: `<strong>${meta.label}</strong> — ${meta.summaries[d.state]}`,
          time: '2 hours ago',
        });
      } else if (d.state === 'DEGRADING') {
        alerts.push({
          level: 'warning',
          text: `<strong>${meta.label}</strong> — ${meta.summaries[d.state]}`,
          time: '4 hours ago',
        });
      } else if (d.state === 'WATCH') {
        alerts.push({
          level: 'info',
          text: `<strong>${meta.label}</strong> — ${meta.summaries[d.state]}`,
          time: '6 hours ago',
        });
      }
    });

    // System alert
    alerts.push({
      level: 'info',
      text: '<strong>Shadow Mode Active</strong> — AI is logging decisions but not executing. You control all actions.',
      time: 'Always',
    });

    list.innerHTML = alerts.map(a => `
      <div class="notif-item" onclick="navigateTo('health'); toggleNotifications();">
        <div class="notif-dot-indicator ${a.level}"></div>
        <div class="notif-text">${a.text}</div>
        <div class="notif-time">${a.time}</div>
      </div>`).join('');
  }
}

// Close dropdown when clicking outside
document.addEventListener('click', (e) => {
  const notif = document.querySelector('.topbar-notification');
  if (notif && !notif.contains(e.target)) {
    document.getElementById('notif-dropdown').classList.remove('show');
  }
});

// ═══════════════════════════════════════════════════════════════════
//  Init
// ═══════════════════════════════════════════════════════════════════

document.addEventListener('DOMContentLoaded', () => {
  initPolicyPack();
  renderOverview();
  renderHealth();
  renderInsights();
  renderActions();
  renderCompetitive();
});
