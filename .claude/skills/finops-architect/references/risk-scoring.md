# Risk Scoring — The Math

Every `Finding` receives a `risk_score` in `[0, 100]`. The aggregate `overall_risk` is the volume-weighted mean, capped at 100.

## Per-finding formula

```
risk_score = severity_weight × confidence × (1 + cost_factor) × 10
clamp(0, 100)
```

| Term | Range | Source |
|---|---|---|
| `severity_weight` | 1 (LOW) / 3 (MEDIUM) / 8 (HIGH) | rule definition |
| `confidence` | 0.0–1.0 | how reliably the rule fires; CPU<5% for 14d → 0.9; stopped instance → 1.0 |
| `cost_factor` | 0.0–2.0 | `min(monthly_cost_usd / 100, 2.0)` — saturates at $200/mo |

## Aggregate formula

```
overall_risk = clamp(0, 100,
  Σ(risk_score_i × weight_i) / Σ(weight_i)
)
where weight_i = max(monthly_cost_i, 1)  # avoid divide-by-zero
```

This **volume-weights** by cost: a single $500/mo idle RDS dominates 50 findings of $1/mo dangling EIPs, which is the right priority for an executive readout.

## Calibration anchors

| overall_risk | What it means | Action |
|---|---|---|
| 0–30 | Healthy hygiene | Quarterly scan is enough |
| 31–60 | Attention | Monthly scan; auto-alert on new HIGHs |
| 61–80 | Significant waste | Weekly scan; named owner per top finding |
| 81–100 | Critical | Daily scan; halt new infra provisioning until cleaned |

## Why not a simple sum?

Sum scales with account size, breaking comparability. A 10,000-resource account *will* have more findings than a 100-resource account; that doesn't mean its hygiene is worse. The bounded average lets us compare risk across accounts of any size — which is what FinOps governance actually needs.
