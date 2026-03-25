# Ernesto Platform Runbook

## Variables de Entorno Obligatorias

- SUPABASE_URL=<url_supabase>
- SUPABASE_ANON_KEY=<anon_key>

Variables recomendadas para control operativo:

- CHAIN_FETCH_MAX_WORKERS=6
- PROVIDER_QUOTA_TOTAL_PER_MIN=240
- PROVIDER_QUOTA_RESERVED_LIVE_SCANNING=160
- PROVIDER_QUOTA_BACKGROUND=80
- PROVIDER_QUOTA_HIGH_WATERMARK=0.85
- PROVIDER_CIRCUIT_FAILURE_THRESHOLD=5
- PROVIDER_CIRCUIT_RECOVERY_TIMEOUT_SEC=90
- LOG_RETENTION_DAYS=30
- ERROR_BUDGET_MAX_ERROR_RATE_PCT_7D=2.0

## Proveedor de Datos

El proveedor de datos es yfinance (unico).

1. Verificar SUPABASE_URL y SUPABASE_ANON_KEY presentes.
2. Reiniciar proceso Streamlit.
3. Confirmar en logs: provider=yfinance.

## Limpieza de Cache por Ticker

Desde codigo:

```python
from infrastructure.data.yahoo_finance_client import limpiar_cache_ticker
limpiar_cache_ticker("SPY")

```

Prefijos de cache estandarizados:

- market:{version}:{provider}:price:{ticker}
- market:{version}:{provider}:exp:{ticker}
- market:{version}:{provider}:chain:{ticker}:{exp}

Versiones recomendadas:

- MARKET_CACHE_VERSION=v1
- MARKET_SCHEMA_VERSION=v1
- SNAPSHOT_SCHEMA_VERSION=v1

## CI/CD Enterprise (Paso 6)

Pipelines en GitHub Actions:

- .github/workflows/ci.yml
- .github/workflows/deploy.yml
- .github/workflows/weekly-health.yml

Etapas criticas bloqueantes:

1. Lint + static checks
2. Unit tests + provider contract tests
3. Smoke scan
4. Deploy staging + E2E
5. Canary production + monitor reforzado

Rollback automatico:

- Si falla staging/prod/canary se ejecuta scripts/rollback_release.py.

## Health Checks Activos

Comando:

```bash
python scripts/healthcheck.py

```

Checks publicados:

- provider (incluye estado del circuito de proteccion)
- cache backend
- repository backend

## Seguridad y Compliance

Artefactos:

- docs/SECURITY_COMPLIANCE_CHECKLIST.md
- docs/INCIDENT_RUNBOOK.md
- docs/SLO_SLA_ERROR_BUDGET.md
- docs/OPERATIONS_DAILY.md

Controles principales:

- fail fast por secretos criticos faltantes
- sanitizacion de errores para UI
- redaccion de secretos en logs
- anonimizacion de identificadores de usuario
- auditoria de cambios en configuracion critica
