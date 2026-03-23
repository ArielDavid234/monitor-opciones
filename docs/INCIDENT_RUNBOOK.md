# Incident Runbook 24x7

## Severidades

- P1: scanner caido, proveedor inoperable, o errores criticos de lectura/escritura multi-tenant.
- P2: degradacion sostenida de SLO (latencia, error rate, calidad de datos, cache).

## Matriz de Respuesta

| Rol | Responsable | Tiempo de respuesta | Responsabilidades |
|---|---|---|---|
| Incident Commander | On-call Platform Lead | <= 5 min | Coordinar mitigacion, priorizar decisiones, aprobar rollback |
| Data/Provider Engineer | On-call Data Engineer | <= 10 min | Diagnosticar proveedor, circuit breaker, schema/data contracts |
| SRE | On-call SRE | <= 10 min | Capacidad, latencia, cache backend, despliegue y rollback release |
| Product Owner | Owner/Admin de plataforma | <= 15 min | Comunicacion a stakeholders, aprobacion de cambios de riesgo |

## Incidente: 429 Sostenido

Objetivo: recuperar cuota util y mantener continuidad en modo degradado controlado.

1. (0-5 min, Data Engineer) Confirmar provider_429_5m, provider_request_denied_count y usage_ratio en telemetria.
2. (5-10 min, SRE) Reducir CHAIN_FETCH_MAX_WORKERS entre 1 y 2 niveles y verificar descenso de 429.
3. (10-15 min, Platform Lead) Mantener snapshot pipeline activo y evitar invalidaciones agresivas de cache.
4. (15-20 min, Platform Lead) Si persiste, conmutar proveedor de fallback segun flag de entorno.
5. (20+ min, Incident Commander) Escalar a proveedor externo y abrir ticket de incidencia con evidencias.

## Incidente: Latencia Fuera de SLO

Objetivo: restaurar p90 por debajo del objetivo del plan sin cortar servicio.

1. (0-5 min, SRE) Ejecutar chequeo de salud y validar estado de cache/proveedor/circuit breaker.
2. (5-10 min, Data Engineer) Confirmar fuente live/cache por ticker y tamano de lotes activos.
3. (10-15 min, SRE) Ajustar ventanas de frescura y reducir paralelismo de fetch.
4. (15-20 min, Platform Lead) Si no recupera, rollback a release estable previa.
5. (20+ min, Incident Commander) Comunicar ETA y estado cada 15 min hasta normalizacion.

## Incidente: Caida de Proveedor

Objetivo: mantener continuidad con fallback y datos degradados consistentes.

1. (0-5 min, Data Engineer) Confirmar outage del proveedor y estado del circuito.
2. (5-10 min, Platform Lead) Activar modo degradado con snapshots/cache.
3. (10-15 min, Platform Lead) Cambiar a proveedor fallback permitido por configuracion.
4. (15-30 min, SRE) Verificar recuperacion de endpoints criticos y tasa de error.
5. (cada 15 min, Product Owner) Publicar update de incidente hasta cierre.

## Incidente: Fallo de Cache

Objetivo: recuperar lecturas/escrituras estables y preservar aislamiento por tenant.

1. (0-5 min, SRE) Validar probe de lectura/escritura de cache y backend activo.
2. (5-10 min, SRE) Si Redis cae, confirmar fallback diskcache funcional.
3. (10-15 min, Data Engineer) Limpiar solo prefijos afectados por tenant y version.
4. (15-20 min, Platform Lead) Reiniciar servicio solo si persiste corrupcion.
5. (20+ min, Incident Commander) Documentar impacto por tenant y acciones preventivas.

## Rollback de Modelo

Objetivo: regresar rapidamente a version de modelo estable.

1. (0-5 min, Owner/Admin) Ejecutar rollback de version en registry.
2. (5-10 min, Data Engineer) Validar estado prod del modelo objetivo.
3. (10-15 min, Platform Lead) Confirmar metricas de drift y score normalizadas.
4. (15+ min, Product Owner) Comunicar cierre y crear accion de mejora.

## Rollback de Release

Objetivo: restaurar release estable sin degradar contratos del scanner.

1. (0-5 min, SRE) Congelar cambios no criticos.
2. (5-10 min, SRE) Ejecutar rollback al artefacto release previo.
3. (10-15 min, Platform Lead) Validar health global, contratos API v1 y smoke tests.
4. (15-20 min, Data Engineer) Verificar columnas y salidas del scanner sin regresion.
5. (20+ min, Incident Commander) Cerrar incidente y abrir postmortem <= 24h.

## Criterios de Escalamiento

- P1 sin resolucion > 10 min.
- Error rate > 2% durante 15 min.
- p90 sobre SLO por 30 min.
- Fallo de contratos de datos en 3 ciclos consecutivos.

## Checklist de Cierre

- Causa raiz identificada y registrada.
- Mitigacion aplicada y validada.
- Auditoria completada (config/model/provider/RBAC).
- Riesgo residual documentado.
- Ticket de postmortem creado.
