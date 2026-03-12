# PROGRESS.md
> Archivo de contexto para desarrollo. Actualizar al completar cada tarea.
> Estado actual del proyecto al inicio de cada sesión.

---

## Estado actual

**Fase:** PROYECTO COMPLETO - Todas las fases implementadas y testeadas
**Versión del documento de planificación:** v2.5
**Última actualización:** 11 Marzo 2026 — Panel SA: agregada opción Editar suscripción (estado, fecha vencimiento, valor mensual, observaciones) en `suscripciones.html` + endpoint `POST /panel/sa/suscripciones/{id}/editar` en `views.py`. Servidor local levantado con `.venv` local via `uvicorn` con `--reload`.

---

## Fase 0 — Fundamentos (Semana 1-2)

- [x] Crear repositorio en GitHub
- [x] Configurar entorno Python local (venv, dependencias del requirements.txt)
- [x] Crear proyecto en Supabase (PostgreSQL + Auth) — credenciales en .env
- [x] Crear todas las tablas en la base de datos — `migrations/001_initial_schema.sql` ejecutado en Supabase
- [x] Configurar FastAPI básico con conexión a Supabase — `main.py`, `config.py`, `database.py`
- [x] Login funcional con Supabase Auth — `routers/auth.py`
- [x] `dependencies.py` — `get_current_user`, `require_role`, `require_superadmin` operativos con ES256 via JWKS
- [x] `middleware/tenant.py` — inyección de `conjunto_id` y verificación suscripción. Arreglado para ES256.
- [x] Deploy inicial en Railway / Uvicorn local operativo — servidor corre en http://localhost:8000
- [x] Entorno local confirmado: `.venv` en raíz del proyecto, arrancar con `.venv\Scripts\python.exe -m uvicorn ph_saas.main:app --host 0.0.0.0 --port 8000 --reload` (Python de sistema 3.14 no tiene los paquetes)
- [x] Usuario superadmin creado en Supabase Auth — `vccompany011@email.com` (UUID: `0703bb43-4423-4c4e-8741-036b6995843b`)

---

## Fase 1 — Core Administrativo (Semana 3-6)

- [x] CRUD de Conjuntos (SuperAdmin) — `routers/conjuntos.py`
- [x] CRUD de Propiedades por conjunto — `routers/propiedades.py`
- [x] CRUD de Usuarios y asignación de roles — `routers/conjuntos.py` (sub-rutas `/api/usuarios`)
- [x] Configuración por conjunto (cuota, tasas, fechas) — `routers/conjuntos.py` (sub-rutas `/api/configuracion`)
- [x] Gestión de Suscripciones SaaS — `routers/suscripciones.py`
- [x] Tests de endpoints — todos pasan: health, auth (login/me/401/422), conjuntos CRUD, suscripciones, propiedades, cleanup → `test_endpoints.py` 7/7 secciones ✅
- [x] Tests de pantallas HTML — `test_panel.py` 29/29 pruebas ✅ (login, conjuntos SA, suscripciones SA, panel app, logout)
- [x] Editar suscripción desde panel SA — modal con estado/fecha/valor/observaciones + `POST /panel/sa/suscripciones/{id}/editar`
- [x] Pantallas HTML basicas con Tailwind

---

## Fase 2 — Cuotas y Pagos (Semana 7-10)

- [x] Generación manual de cuotas (un mes a la vez) — `services/cuota_service.py` + `routers/cuotas.py`
- [x] Registro de pagos con detalle por cuota — `services/pago_service.py` + `routers/pagos.py`
- [x] Manejo de saldos a favor — `pago_service.aplicar_saldo_a_favor()` + `GET/POST /api/saldos-a-favor`
- [x] Movimientos contables automáticos — creados en `pago_service` al registrar cada pago
- [x] APScheduler: job diario medianoche → marcar cuotas `Vencida` — `cuota_service.marcar_cuotas_vencidas()` conectado
- [x] Endpoints `/internal/generar-cuotas` y `/internal/calcular-intereses` con `X-Internal-Token` — `routers/internal.py`
- [ ] Configurar cron-job.org → `/internal/generar-cuotas` día 1
- [ ] Configurar cron-job.org → `/internal/calcular-intereses` día 5
- [ ] Configurar cron-job.org → `/internal/notificar-mora` día `dia_notificacion_mora` por conjunto

---

## Fase 3 — Cartera y Reportes (Semana 11-13) ✅ COMPLETA

- [x] Vista de cartera por conjunto — `GET /api/cartera` → `services/cartera_service.py` + `routers/cartera.py`
- [x] Estado de cuenta por propiedad — `GET /api/cartera/propiedad/{id}` + antigüedad `GET /api/cartera/antiguedad`
- [x] Generación de PDFs (paz y salvo, estado de cuenta, cartera) — WeasyPrint + `services/pdf_service.py` + `routers/reportes.py`
- [x] Tests Fase 3 — `test_fase3.py` 8 secciones, todos pasan ✅ (PDFs salteados en Windows, funcionan en Railway)

---

## Fase 4 — Notificaciones (Semana 14-15) ✅ COMPLETA

- [x] Integración Twilio WhatsApp (modo degradado sin credenciales en dev, funciona con credenciales en Railway)
- [x] Notificación de cuota generada — hook en `generar_cuotas_todos` + `notificar_cuotas_generadas()`
- [x] Recordatorio de mora — endpoint `POST /internal/notificar-mora` + `notificar_mora_conjunto()`
- [x] Confirmación de pago — hook en `registrar_pago` + `notificar_confirmacion_pago()`
- [x] Mensaje de paz y salvo — hook en `reporte_paz_y_salvo` + `notificar_paz_y_salvo()`
- [x] Tests Fase 4 — `test_fase4.py` 7 secciones, todos pasan ✅

---

## Archivos creados

| Archivo | Estado |
|---|---|
| `PROYECTO_PH_SAAS.md` | ✅ Completo v2.5 |
| `ARCHITECTURE.md` | ✅ Creado |
| `DATABASE.md` | ✅ Creado |
| `RULES.md` | ✅ Creado |
| `CONVENTIONS.md` | ✅ Creado |
| `PROGRESS.md` | ✅ Creado |
| `requirements.txt` | ✅ Creado |
| `.env.example` | ✅ Creado |
| `.gitignore` | ✅ Actualizado |
| `migrations/001_initial_schema.sql` | ✅ Creado y ejecutado en Supabase |
| `migrations/002_fix_conjunto_nombre_unique.sql` | ✅ Creado — pendiente ejecutar en Supabase (reemplaza UNIQUE por índice parcial WHERE is_deleted=FALSE) |
| `ph_saas/__init__.py` | ✅ Creado |
| `ph_saas/main.py` | ✅ Creado — actualizado Fase 2: routers cuotas, pagos, internal registrados |
| `ph_saas/config.py` | ✅ Creado |
| `ph_saas/database.py` | ✅ Creado |
| `ph_saas/scheduler.py` | ✅ Creado (job diario medianoche) |
| `ph_saas/dependencies.py` | ✅ Creado (`get_current_user`, `require_role`, `require_superadmin`) |
| `ph_saas/errors.py` | ✅ Creado (`ErrorMsg` + helpers `http_4xx`) |
| `ph_saas/middleware/tenant.py` | ✅ Creado — aislamiento tenant + verificación suscripción |
| `ph_saas/models/base.py` | ✅ Creado |
| `ph_saas/models/conjunto.py` | ✅ Creado |
| `ph_saas/models/usuario.py` | ✅ Creado |
| `ph_saas/models/usuario_conjunto.py` | ✅ Creado |
| `ph_saas/models/suscripcion.py` | ✅ Creado |
| `ph_saas/models/propiedad.py` | ✅ Creado |
| `ph_saas/models/configuracion_conjunto.py` | ✅ Creado |
| `ph_saas/models/cuota.py` | ✅ Creado |
| `ph_saas/models/pago.py` | ✅ Creado |
| `ph_saas/models/pago_detalle.py` | ✅ Creado |
| `ph_saas/models/saldo_a_favor.py` | ✅ Creado |
| `ph_saas/models/movimiento_contable.py` | ✅ Creado |
| `ph_saas/models/proceso_log.py` | ✅ Creado |
| `ph_saas/models/cuota_interes_log.py` | ✅ Creado |
| `ph_saas/routers/auth.py` | ✅ Creado (`/auth/login`, `/auth/logout`, `/auth/me`) |
| `ph_saas/schemas/cuota.py` | ✅ Creado (CuotaOut, CuotaDetalle, CuotaGenerarRequest) |
| `ph_saas/schemas/pago.py` | ✅ Creado (PagoCreate, PagoOut, PagoConDetalle, PagoDetalleIn/Out, SaldoAFavorOut, AplicarSaldoRequest) |
| `ph_saas/services/cuota_service.py` | ✅ Creado (generar_cuotas, calcular_intereses, marcar_cuotas_vencidas) |
| `ph_saas/services/pago_service.py` | ✅ Creado (registrar_pago, anular_pago, aplicar_saldo_a_favor, notificar_confirmacion_pago) |
| `ph_saas/routers/cuotas.py` | ✅ Creado (GET/POST endpoints cuotas) |
| `ph_saas/routers/pagos.py` | ✅ Creado (GET/POST/DELETE pagos + saldos a favor) |
| `ph_saas/routers/internal.py` | ✅ Creado (/internal/generar-cuotas, /internal/calcular-intereses, /internal/notificar-mora) |
| `ph_saas/schemas/conjunto.py` | ✅ Creado (ConjuntoCreate/Update/Out/Detalle, SuscripcionCreate/Out) |
| `ph_saas/schemas/propiedad.py` | ✅ Creado (PropiedadCreate/Update/Out/Detalle) |
| `ph_saas/schemas/usuario.py` | ✅ Creado (UsuarioCreate/Update/Out, UsuarioConjuntoOut, CambiarRolBody) |
| `ph_saas/schemas/configuracion.py` | ✅ Creado (ConfiguracionOut/Update) |
| `ph_saas/routers/conjuntos.py` | ✅ Creado (CRUD conjuntos SA, usuarios AD, configuración AD/CO) |
| `ph_saas/routers/propiedades.py` | ✅ Creado (CRUD propiedades por conjunto) |
| `ph_saas/routers/suscripciones.py` | ✅ Creado (gestión SaaS SA, ver vencimiento AD) |
| `ph_saas/routers/views.py` | ✅ Actualizado — agregado `POST /panel/sa/suscripciones/{id}/editar` |
| `ph_saas/templates/base.html` | ✅ Creado (sidebar Tailwind + Alpine.js) |
| `ph_saas/templates/login.html` | ✅ Creado |
| `ph_saas/templates/sa/conjuntos.html` | ✅ Creado |
| `ph_saas/templates/sa/suscripciones.html` | ✅ Actualizado — botón Editar + modal edición suscripción |
| `ph_saas/templates/app/propiedades.html` | ✅ Creado |
| `test_fase2.py` | ✅ Suite de tests Fase 2 — 11 secciones, todos pasaron |
| `ph_saas/schemas/cartera.py` | ✅ Creado (ResumenCartera, EstadoCuentaPropiedad, CarteraAntiguedadItem) |
| `ph_saas/services/cartera_service.py` | ✅ Creado (get_resumen_cartera, get_estado_cuenta, get_cartera_antiguedad) |
| `ph_saas/routers/cartera.py` | ✅ Creado (GET /api/cartera, /api/cartera/antiguedad, /api/cartera/propiedad/{id}) |
| `ph_saas/services/pdf_service.py` | ✅ Creado (generar_estado_cuenta_pdf, generar_paz_y_salvo_pdf, generar_cartera_pdf) |
| `ph_saas/routers/reportes.py` | ✅ Creado (GET /api/reportes/estado-cuenta, /paz-y-salvo, /cartera) + hook WS notificar_paz_y_salvo |
| `ph_saas/templates/pdf/estado_cuenta.html` | ✅ Creado |
| `ph_saas/templates/pdf/paz_y_salvo.html` | ✅ Creado |
| `ph_saas/templates/pdf/cartera.html` | ✅ Creado |
| `ph_saas/templates/app/usuarios.html` | ✅ Creado |
| `ph_saas/templates/app/configuracion.html` | ✅ Creado |
| `ph_saas/templates/app/propietarios.html` | ✅ Creado (lista + modales crear/editar/eliminar) |
| `ph_saas/templates/sa/usuarios.html` | ✅ Creado (lista usuarios SA + modales crear/cambiar rol/eliminar) |
| `setup_usuarios_prueba.py` | ✅ Creado — setup idempotente de 3 usuarios de prueba (Admin/Contador/Porteria) |
| `test_fase3.py` | ✅ Suite de tests Fase 3 — 8 secciones, todos pasaron |
| `ph_saas/services/whatsapp_service.py` | ✅ Creado (Twilio WA, modo degradado, notificar_cuotas_generadas, mora, pago, paz_y_salvo) |
| `test_fase4.py` | ✅ Suite de tests Fase 4 — 7 secciones, todos pasaron |

---

## Decisiones de diseño tomadas (no reabrir)

| Decisión | Elección |
|---|---|
| Stack | Python + FastAPI + Supabase + HTMX |
| Multi-tenant | shared DB + conjunto_id en código |
| Cálculo de interés | Simple mensual sobre saldo capital |
| Imputación de abonos | Primero interés, luego capital |
| Idempotencia intereses | Tabla `cuota_interes_log` |
| Fecha vencimiento cuota | Último día del mes del periodo |
| Trigger generación cuotas | cron-job.org día 1 (no APScheduler) |
| Python 3.14 + SQLAlchemy 2.0.35 | `from __future__ import annotations` en todos los modelos — resuelve incompatibilidad de tipos `X \| Y` |
| Saldo a favor excedente | Split automático en transacción atómica |
| WeasyPrint import lazy | `from weasyprint import HTML` dentro de cada función (no a nivel de módulo) — evita fallo en Windows sin GTK. En Railway (Linux) funciona en runtime |
| Notificaciones | Solo WhatsApp via Twilio |
| Cobro SaaS | Transferencia manual mensual |
| Supabase JWT (ES256) | Proyectos nuevos de Supabase usan ES256 (ECDSA), no HS256. Verificación via JWKS: `{SUPABASE_URL}/auth/v1/.well-known/jwks.json`. Cacheado al startup. |
| TenantMiddleware + async | `_decode_jwt()` se llama via `asyncio.to_thread()` para no bloquear el event loop desde el middleware async |
| Body POST conjuntos | `suscripcion` es campo opcional dentro de `ConjuntoCreate` (no parámetro separado) para evitar el modo "embedded body" de FastAPI |

---

## Deudas técnicas conocidas (no bloquean Fase 1)

1. `saldo_a_favor_detalle` — pagos masivos con múltiples cuotas en una operación
2. 2FA para SuperAdmin — activar en Supabase Auth antes de escalar
3. RLS PostgreSQL — modelo compatible, activar cuando escale
4. Cron dinámico por conjunto — usar `dia_generacion_cuota` cuando se implemente
5. Integración Wompi — cobro automático SaaS para +10 conjuntos
6. JWKS cache — actualmente en memoria del proceso; al reiniciar se recarga. Para producción con múltiples workers, considerar Redis o cache persistente.
7. ~~Scripts de debug en raíz — `debug_auth.py`, `create_superadmin.py`, `fix_superadmin.py`, `debug_jwt.py`, `debug_jwt2.py`, `debug_direct.py`~~ — **ELIMINADOS** (limpieza Fase 4).

---

## Instrucciones para Claude al inicio de cada sesión

Al comenzar una nueva sesión de desarrollo, pedir a Claude que lea:
1. `PROGRESS.md` — para saber en qué punto está el proyecto
2. `RULES.md` — antes de implementar cualquier service
3. `DATABASE.md` — antes de crear modelos o migraciones
4. `CONVENTIONS.md` — antes de crear archivos o funciones
5. `ARCHITECTURE.md` — si hay dudas sobre estructura o flujos
