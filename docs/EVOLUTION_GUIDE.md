# V3 Evolution Guide

## Purpose
How to make changes to V3 without breaking architectural coherence.
Follow this for any non-trivial change.

## The Five-Step Change Process

### Step 1: Write an ADR draft
Before code, copy `docs/adr/template.md` and answer:
- What are you trying to do?
- What alternatives did you consider?
- What are you giving up?

If you cannot articulate alternatives, the change may not be
architecturally significant — proceed without an ADR.

### Step 2: Check contracts
Does your change affect a typed object in `contracts.py`?
- If backward-compatible (add fields, don't remove): proceed
- Otherwise: write a new ADR superseding the old one AND update
  contract tests in `tests/contracts/`

### Step 3: Locate in PHASE_ROADMAP.md
Find where your change fits.
- If not in roadmap: add it
- If in a later phase: reconsider whether now is the right time
- If in a different track of Phase 2: confirm you have the right
  blocking conditions

### Step 4: Write or update tests first
- New typed object: contract test before implementation
- New module: acceptance test for the module
- Behavior change: update affected tests to reflect new expectation

### Step 5: Implement and verify
- Minimum change needed
- Run full suite: `pytest tests/ -v`
- Run invariants: `pytest tests/architecture/ -v`
- Any invariant failure: fix code OR write new ADR superseding the
  governing one

## Adding Business Content (KG, Policies, Brand Data)
Business content is not architecture. No ADR needed for:
- Adding a new brand's KG facts
- Adjusting policy weights
- Loading new data

Just:
1. Put content in `fixtures/` or `playbooks/`
2. Ensure content passes existing contract tests
3. Run test suite

## Adding a New Data Source (Phase 2 Track A or Phase 3)
Write an ADR before implementing. Document:
- What fields are extracted
- Defaults for missing data
- Error modes handled
- Where in the pipeline data flows

## Adding a New Module (Phase 2 Track B or Phase 3)
1. Write ADR specifying which layer it belongs to and why
2. Add to PHASE_ROADMAP.md in correct phase/track
3. Update CLAUDE.md architecture section
4. Add architecture invariant tests for its boundaries
5. Write implementation and unit tests

## Working in Phase 2 Dual-Track Mode
Phase 2 has two parallel tracks (see ADR-0006 and PHASE_ROADMAP.md).

When picking up work:
1. Identify which track the task belongs to (Track A: commercial,
   Track B: architecture/KG)
2. Check track entry conditions are met
3. Check the task is not blocked by another item in the same track
4. Track A tasks may proceed even if Track B is incomplete (and vice
   versa)
5. Phase 3 entry requires both tracks complete

## When Things Go Wrong
- Test failure on existing test: do not delete it. Investigate.
- Architecture invariant failure: do not bypass it. Fix or supersede.
- Contract test failure: the type was changed. Update contract test
  AND write new ADR.
- Multiple ADRs cite the same code: that's fine. Cross-references
  are good.
