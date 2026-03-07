# PROGRESS.md
> Archivo de contexto para desarrollo. Actualizar al completar cada tarea.
> Estado actual del proyecto al inicio de cada sesión.

---

## Estado actual

**Fase:** Fase 1 COMPLETA — todos los endpoints implementados + pantallas HTML Tailwind operativas + test suite completo ✅
**Versión del documento de planificación:** v2.5
**Última actualización:** 7 Marzo 2026 — Tests completos: test_endpoints.py (7/7 secciones) y test_panel.py (29/29). Bug fix: 500 en POST /admin/conjuntos con nombre de registro soft-deleted. Migración 002 escrita.

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
- [x] Pantallas HTML basicas con Tailwind

---

## Fase 2 — Cuotas y Pagos (Semana 7-10)

- [ ] Generación manual de cuotas (un mes a la vez)
- [ ] Registro de pagos con detalle por cuota
- [ ] Manejo de saldos a favor
- [ ] Movimientos contables automáticos
- [ ] Configurar cron-job.org → `/internal/generar-cuotas` día 1
- [ ] APScheduler: job diario medianoche → marcar cuotas `Vencida`

---

## Fase 3 — Cartera y Reportes (Semana 11-13)

- [ ] Vista de cartera por conjunto
- [ ] Estado de cuenta por propiedad
- [ ] Generación de PDFs (paz y salvo, estado de cuenta)
- [ ] Endpoint `/internal/calcular-intereses` con idempotencia via `cuota_interes_log`
- [ ] Configurar cron-job.org → `/internal/calcular-intereses` día 5
- [ ] Cálculo y aplicación de intereses de mora

---

## Fase 4 — Notificaciones (Semana 14-15)

- [ ] Integración Twilio WhatsApp (pruebas en sandbox)
- [ ] Notificación de cuota generada
- [ ] Notificación de mora
- [ ] Confirmación de pago

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
| `ph_saas/main.py` | ✅ Creado |
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
| `ph_saas/schemas/conjunto.py` | ✅ Creado (ConjuntoCreate/Update/Out/Detalle, SuscripcionCreate/Out) |
| `ph_saas/schemas/propiedad.py` | ✅ Creado (PropiedadCreate/Update/Out/Detalle) |
| `ph_saas/schemas/usuario.py` | ✅ Creado (UsuarioCreate/Update/Out, UsuarioConjuntoOut, CambiarRolBody) |
| `ph_saas/schemas/configuracion.py` | ✅ Creado (ConfiguracionOut/Update) |
| `ph_saas/routers/conjuntos.py` | ✅ Creado (CRUD conjuntos SA, usuarios AD, configuración AD/CO) |
| `ph_saas/routers/propiedades.py` | ✅ Creado (CRUD propiedades por conjunto) |
| `ph_saas/routers/suscripciones.py` | ✅ Creado (gestión SaaS SA, ver vencimiento AD) |
| `ph_saas/routers/views.py` | ✅ Creado (pantallas HTML — login, SA, AD) |
| `ph_saas/templates/base.html` | ✅ Creado (sidebar Tailwind + Alpine.js) |
| `ph_saas/templates/login.html` | ✅ Creado |
| `ph_saas/templates/sa/conjuntos.html` | ✅ Creado |
| `ph_saas/templates/sa/suscripciones.html` | ✅ Creado |
| `ph_saas/templates/app/propiedades.html` | ✅ Creado |
| `ph_saas/templates/app/usuarios.html` | ✅ Creado |
| `ph_saas/templates/app/configuracion.html` | ✅ Creado |

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
| dia_generacion_cuota UI | Oculto, reservado fase futura |
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
7. Scripts de debug en raíz — `debug_auth.py`, `create_superadmin.py`, `fix_superadmin.py`, `debug_jwt.py`, `debug_jwt2.py`, `debug_direct.py` — eliminar antes del deploy a producción.

---

## Instrucciones para Claude al inicio de cada sesión

Al comenzar una nueva sesión de desarrollo, pedir a Claude que lea:
1. `PROGRESS.md` — para saber en qué punto está el proyecto
2. `RULES.md` — antes de implementar cualquier service
3. `DATABASE.md` — antes de crear modelos o migraciones
4. `CONVENTIONS.md` — antes de crear archivos o funciones
5. `ARCHITECTURE.md` — si hay dudas sobre estructura o flujos
