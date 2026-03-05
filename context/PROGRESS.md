# PROGRESS.md
> Archivo de contexto para desarrollo. Actualizar al completar cada tarea.
> Estado actual del proyecto al inicio de cada sesión.

---

## Estado actual

**Fase:** Planificación completada — lista para iniciar Fase 0
**Versión del documento de planificación:** v2.5
**Última actualización:** Marzo 2026 — Fase 0 en progreso (código base creado, pendiente: GitHub, venv, ejecutar migración SQL, Railway deploy)

---

## Fase 0 — Fundamentos (Semana 1-2)

- [ ] Crear repositorio en GitHub
- [ ] Configurar entorno Python local (venv, dependencias del requirements.txt)
- [x] Crear proyecto en Supabase (PostgreSQL + Auth) ← credenciales en .env
- [x] Crear todas las tablas en la base de datos ← `migrations/001_initial_schema.sql` listo para ejecutar en Supabase
- [x] Configurar FastAPI básico con conexión a Supabase ← `main.py`, `config.py`, `database.py`
- [x] Login funcional con Supabase Auth ← `routers/auth.py`
- [x] `dependencies.py` — `get_current_user`, `require_role` operativos
- [x] `middleware/tenant.py` — inyección de `conjunto_id` y verificación suscripción ⚠️
- [ ] Deploy inicial en Railway

---

## Fase 1 — Core Administrativo (Semana 3-6)

- [ ] CRUD de Conjuntos (SuperAdmin)
- [ ] CRUD de Propiedades por conjunto
- [ ] CRUD de Usuarios y asignación de roles
- [ ] Configuración por conjunto (cuota, tasas, fechas)
- [ ] Pantallas HTML básicas con Tailwind

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
| `migrations/001_initial_schema.sql` | ✅ Creado — pendiente ejecutar en Supabase |
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
| Seguridad SuperAdmin Fase 1 | JWT superadmin (2FA en fase futura) |
| Saldo a favor excedente | Split automático en transacción atómica |
| dia_generacion_cuota UI | Oculto, reservado fase futura |
| Notificaciones | Solo WhatsApp via Twilio |
| Cobro SaaS | Transferencia manual mensual |

---

## Deudas técnicas conocidas (no bloquean Fase 1)

1. `saldo_a_favor_detalle` — pagos masivos con múltiples cuotas en una operación
2. 2FA para SuperAdmin — activar en Supabase Auth antes de escalar
3. RLS PostgreSQL — modelo compatible, activar cuando escale
4. Cron dinámico por conjunto — usar `dia_generacion_cuota` cuando se implemente
5. Integración Wompi — cobro automático SaaS para +10 conjuntos

---

## Instrucciones para Claude al inicio de cada sesión

Al comenzar una nueva sesión de desarrollo, pedir a Claude que lea:
1. `PROGRESS.md` — para saber en qué punto está el proyecto
2. `RULES.md` — antes de implementar cualquier service
3. `DATABASE.md` — antes de crear modelos o migraciones
4. `CONVENTIONS.md` — antes de crear archivos o funciones
5. `ARCHITECTURE.md` — si hay dudas sobre estructura o flujos
