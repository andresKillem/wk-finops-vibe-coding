# Detection Rules — Catalog

Each rule encodes one well-known FinOps anti-pattern. Thresholds are **opinionated defaults**; adjust per account profile. All rules emit a `Finding` with `severity`, `savings_estimate`, and a citation.

| Rule ID | Resource | Trigger | Severity | Default monthly savings citation |
|---|---|---|---|---|
| `R-EBS-001` | EBS Volume | `state == "available"` for ≥7d (no attached EC2) | HIGH | EBS gp3 1TB ≈ $80/mo |
| `R-EC2-001` | EC2 Instance | avg CPU < 5% for 14d AND network < 1MB/d | MEDIUM | varies by family; lookup table in code |
| `R-EC2-002` | EC2 Instance | state `stopped` ≥30d | LOW | only EBS storage cost (~$10/mo per 100GB) |
| `R-EIP-001` | Elastic IP | not associated with running instance | MEDIUM | $3.60/mo per dangling EIP (AWS pricing 2026) |
| `R-NAT-001` | NAT Gateway | bytes_processed < 1MB/d for 7d | HIGH | $32/mo + per-GB; idle NATs are silent killers |
| `R-RDS-001` | RDS Instance | DatabaseConnections == 0 for 7d | HIGH | full instance cost (often $50-500/mo) |
| `R-ELB-001` | Load Balancer (ALB/NLB) | 0 healthy targets for 7d | MEDIUM | $16-22/mo per LB |
| `R-INST-LEGACY-001` | EC2 Instance | family in {t2, m4, r4, c4} | LOW | 10-30% savings migrating to current gen / Graviton |

## Why these and not others?

These eight rules cover ~80% of waste in typical small/mid AWS accounts (per FinOps Foundation 2026 benchmark report). Adding more rules has diminishing returns and increases false-positive rate.

## False-positive guidance

- **EBS volumes intentionally kept** for backup — check tag `Lifecycle=archive` before recommending deletion.
- **Stopped EC2 used for build/dev** — check tag `Environment=dev` and `LastUsed` if instrumented.
- **NAT gateways with bursty traffic** — 7d may be too short for monthly batch jobs; recommend 30d for production accounts.

## Adding a new rule

1. Subclass `DetectionRule` in `src/finops/detection/aws_rules.py` (or `azure_rules.py`).
2. Implement `evaluate(resource, billing_history) -> Optional[Finding]`.
3. Register in `engine.RULES`.
4. Add a fixture-based test in `tests/test_detection.py`.
5. Document here with citation.
