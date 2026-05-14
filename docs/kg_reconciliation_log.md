# KG Reconciliation Log

**Purpose**: Track discrepancies between the KG playbook system and real-world
merchant outcomes. Entries here flag cases where the system's recommendation
diverged from what the partner would have done, or where signal data didn't
match the pattern's expectation.

**When to add an entry**: After any live recommendation is reviewed by a partner
and a discrepancy is identified. Also use for post-mortem after a recommendation
cycle.

**Format**:
```
## [DATE] [BRAND] — [PATTERN_ID]
- Action recommended: <action_id>
- Partner assessment: <agreed / disagreed / partial>
- Discrepancy: <what was wrong — signal, threshold, action, or framing>
- Resolution: <threshold update / pattern update / use case addition / no action>
- Filed by: <who>
```

---

<!-- Add entries below this line -->
