# SLO, SLA and Error Budget

## Service Objectives (SLO)
- Scanner availability: >= 99.5% monthly.
- End-to-end scan latency:
  - p50 <= 3000 ms
  - p90 <= 60000 ms
  - p99 <= 120000 ms
- Max error rate: <= 2.0% rolling 7d.

## Service Commitment (SLA)
- Production incident response:
  - P1 acknowledgement <= 10 minutes.
  - P2 acknowledgement <= 30 minutes.
- Recovery targets:
  - P1 restore service <= 60 minutes.
  - P2 mitigate <= 4 hours.

## Error Budget Policy
- Budget source: rolling 7d error rate (ERROR_RATE_7D_PCT).
- Budget limit: ERROR_BUDGET_MAX_ERROR_RATE_PCT_7D.
- If budget exceeded and CHANGE_FREEZE_ENABLED=true:
  - Block deployments automatically.
  - Only emergency fixes and rollback allowed.
  - Unfreeze after 24h below threshold.
