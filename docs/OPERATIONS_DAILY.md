# Daily Operations Guide

## Start of Shift
1. Run python scripts/validate_environment.py --stage prod.
2. Run python scripts/healthcheck.py and confirm overall is not down.
3. Check latest weekly report in reports/weekly_health/.

## During Shift
1. Monitor scan telemetry and SLO summary logs.
2. Watch provider_429_5m, scan_latency_ms_p90, cache_hit_ratio.
3. If thresholds breached, follow docs/INCIDENT_RUNBOOK.md.

## Change Execution
1. Confirm error budget gate is green.
2. Deploy to staging first, execute E2E liquid/non-liquid tickers.
3. Promote to production canary and monitor canary metrics.
4. Roll back immediately on degradation.

## End of Shift
1. Confirm no open P1/P2 incidents.
2. Document operational anomalies and mitigations.
3. Hand off active risks with next-check timestamp.
