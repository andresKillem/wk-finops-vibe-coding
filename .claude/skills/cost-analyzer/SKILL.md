---
name: cost-analyzer
description: Use when the user has detected findings and asks "what should I prioritize?" or "tell me the executive summary". Triages and ranks waste with a narrative.
when_to_use: After `finops scan`, when the output is too long to read raw. Or when the user asks for an "executive readout", "what's the headline?", or "where do I start?".
---

# Cost Analyzer

Narrow specialist. Takes raw `Finding` records and produces a **prioritized, narrated** view fit for an executive Slack DM. No new detection — only ranking and explanation.

## Procedure

1. Load findings from DB or accept as input.
2. Group by `root_cause`:
   - **Forgotten resources** (orphaned EBS, dangling EIPs) — usually a person who left or a deleted instance left orphans behind.
   - **Idle resources** (idle EC2/RDS/NAT) — overprovisioning, dev environments left running, batch jobs no longer needed.
   - **Outdated families** (legacy generation instances) — migration debt.
3. Compute aggregated savings per group.
4. Rank groups by `total_monthly_savings × confidence`.
5. Pick top 5 individual findings across groups (not top 5 per group — global top 5).
6. Write a 3-bullet executive summary:
   - Bullet 1: total waste in $/month and 12mo projection
   - Bullet 2: dominant root cause and the inferred organizational story behind it
   - Bullet 3: single recommended next action (the cheapest, lowest-blast-radius win)

## Output JSON shape

```json
{
  "executive_narrative": ["...", "...", "..."],
  "by_root_cause": {
    "forgotten_resources": {"total_savings": 0, "count": 0, "examples": []},
    "idle_resources":     {"total_savings": 0, "count": 0, "examples": []},
    "outdated_families":  {"total_savings": 0, "count": 0, "examples": []}
  },
  "top_5": [
    {"finding_id": 0, "title": "", "savings_per_month": 0, "rationale": ""}
  ],
  "recommended_next_action": {
    "finding_ids": [],
    "reasoning": "",
    "expected_savings": 0,
    "blast_radius": "low"
  }
}
```

## Tone guidance

- **Concrete over abstract.** "Three orphaned EBS volumes account for 60% of waste" beats "We see significant storage waste."
- **Narrative over enumeration.** Bullet 2 is *literally a story* — "Likely a deleted EC2 fleet from Q3 left these EBS behind."
- **No CYA hedging.** If the data is clear, say so. If it's mixed, name the mixed signals explicitly.
