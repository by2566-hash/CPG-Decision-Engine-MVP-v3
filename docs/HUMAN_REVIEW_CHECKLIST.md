# V3 Human Review Checklist

## Purpose
Items needing human (you + partner + Tess) confirmation before V3 can be considered Phase 1 production-ready. Bring this to the next sync meeting and mark each item resolved.

---

## A. Data & License (from DATA_AND_LICENSE_STATUS.md)

### A1. Shopify Data - Sheet1.csv provenance
- [ ] Is this real merchant data or synthetic?
- [ ] If real: who is the source brand? Is there an NDA?
- [ ] Can it be shown to investors during funding demo?
- [ ] Is PII present? (If yes, must be scrubbed before any external sharing)
- **Owner**: Aiden + Partner
- **Blocks**: External demo, partner onboarding

### A2. V3 LICENSE file
- [ ] Add a LICENSE file at V3 root (recommend: proprietary or BUSL-1.1)
- [ ] Decide who owns the IP (SHOPLINE, Aiden personally, joint)
- **Owner**: Tess (legal) + Aiden
- **Blocks**: Any open external sharing

---

## B. ADR Rationale Confirmation (from SETUP_COMPLETE_2026_04_09.md)

### B1. ADR-0003 (L3 split deferred)
- [ ] Does the deferral timeline align with partner's KG content delivery schedule?
- [ ] If partner delivers content faster than expected, do we accelerate L3 split?
- **Owner**: Aiden + Partner

### B2. ADR-0006 (Phase 2 dual-track)
- [ ] Does Track A entry condition match actual Shopline API access timeline?
- [ ] Who owns securing Shopline OAuth credentials?
- **Owner**: Aiden + Tess

### B3. BrightSkin fixture realism
- [ ] Is 33% margin representative of real skincare brands?
- [ ] Is 0.61 churn score typical for the demo scenario?
- [ ] If not, update fixture values to match partner's brand expertise
- **Owner**: Partner
- **Note**: This is content, not architecture — fix via Template B if values need adjustment

---

## C. Phase 2 Readiness Gates

### C1. Funding decision
- [ ] Has Tess scheduled the funding demo?
- [ ] Has the funding decision been made?
- [ ] If yes — green light to start Phase 2

### C2. Partner KG delivery format
- [ ] Has partner agreed to deliver KG content in YAML format?
- [ ] Does partner have a sample brand ready (BrightSkin or other)?
- [ ] First content delivery date committed?
- **Owner**: Partner

### C3. Shopline production access
- [ ] Production OAuth app registered?
- [ ] First merchant identified for onboarding?
- [ ] Rate limit quotas confirmed?
- **Owner**: Tess + Aiden

---

## D. Demo Readiness

### D1. demo_brightskin.py output
- [ ] Run `python scripts/demo_brightskin.py` and review output
- [ ] Does the evidence chain look presentable to non-technical leadership?
- [ ] Any output that would confuse Tess in front of investors?
- **Owner**: Aiden (run alone first, then walk through with Tess)

### D2. Slide deck
- [ ] Architecture overview slide (one diagram)
- [ ] Three principles slide (determinism / explainability / human confirmation)
- [ ] Evidence Graph Snapshot example slide (the differentiator)
- [ ] Phase 1 / 2 / 3 roadmap slide
- [ ] Governance slide (ADRs, contract tests — one bullet, not detailed)
- **Owner**: Aiden + Tess

---

## E. Open Questions to Discuss

### E1. KG content scope for Phase 2 first delivery
- How many brands minimum for Track B "complete"? Currently roadmap says 2.
- Do we want 2 deep brands or 5 shallow brands?

### E2. Performance billing trigger
- ADR-0006 says billing is built in Track A but activation deferred until first complete reward cycle. Define "complete reward cycle" — is it 30 days? 60 days? First merchant approval?

### E3. Shadow mode exit criteria
- Phase 1 is shadow mode (was_executed=False always). When does this flip? At first paying customer? After N merchant approvals?

---

## How to Use This Checklist

1. Bring to next sync with partner + Tess
2. Walk through each section, mark resolved items
3. For unresolved items, assign owner + deadline
4. Items marked resolved → update source document (DATA_AND_LICENSE_STATUS.md, fixture file, etc.) and remove from this checklist
5. New questions surfacing during meeting → add to section E
6. Re-review monthly until all resolved

---

**Last updated**: 2026-04-10
**Next review**: After next partner sync