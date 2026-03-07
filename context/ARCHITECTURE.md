# ARCHITECTURE.md
> Archivo de contexto para desarrollo. Leer antes de escribir cualquier código.
> Extraído de PROYECTO_PH_SAAS.md v2.5

---

## Stack tecnológico

| Capa | Tecnología |
|---|---|
| Backend | Python 3.14.3 + FastAPI 0.115.0 |
| Base de datos | PostgreSQL via Supabase |
| Frontend | Jinja2 + Tailwind CSS CDN + Alpine.js CDN |
| Autenticación | Supabase Auth (JWT ES256 via JWKS) |
| PDFs | WeasyPrint |
| Notificaciones | Twilio (WhatsApp) |
| Jobs automáticos | APScheduler + cron-job.org |
| Hosting | Railway |

## Multi-tenant

- Modelo: Shared Database + filtros por `conjunto_id` en código Python
- Cada tabla funcional tiene `conjunto_id UUID NOT NULL`
- El aislamiento se hace en `middleware/tenant.py`, NO en RLS de PostgreSQL (Fase 1)

## Autenticación JWT

- Supabase nuevos proyectos emiten tokens **ES256** (ECDSA), no HS256
- Clave pública obtenida via JWKS: `{SUPABASE_URL}/auth/v1/.well-known/jwks.json`
- JWKS se precarga al startup y se cachea en memoria del proceso (`dependencies.py`)
- `TenantMiddleware` llama `_decode_jwt()` via `asyncio.to_thread()` (no bloquea el event loop)
- Vistas HTML (`/panel/*`) gestionan su propia auth via cookie `ph_token` — no pasan por TenantMiddleware

## Flujo del middleware

```
JWT (Supabase Auth)
      ↓
middleware/tenant.py
      ↓
¿rol == superadmin?
      ├── SÍ → bypass completo
      └── NO ↓
          Extrae conjunto_id del JWT
          ↓
          Verifica suscripcion_saas.estado == 'Activo'
          ↓ (si Suspendido → HTTP 403)
          Inyecta conjunto_id en el contexto del request
          ↓
          Todos los queries filtran por conjunto_id
```

## Roles

| Rol | Scope |
|---|---|
| superadmin | Sistema completo. Claim `role: superadmin` en JWT. Rutas `/admin/*` |
| Administrador | Su conjunto. Ve fecha de vencimiento SaaS (solo lectura) |
| Contador | Pagos, cuotas, reportes. Sin gestión de usuarios |
| Porteria | Solo consulta paz y salvos y estado de cuenta |

Un usuario puede tener roles distintos en conjuntos distintos.

## Jobs automáticos

| Trigger | Qué hace | Cuándo |
|---|---|---|
| cron-job.org → `POST /internal/generar-cuotas` | Genera cuotas del mes | Día 1, 6:00 AM Bogotá |
| cron-job.org → `POST /internal/calcular-intereses` | Calcula mora | Día 5, 6:00 AM Bogotá |
| APScheduler (diario, medianoche) | Marca cuotas como `Vencida` | Diario |

- APScheduler se inicializa con `timezone='America/Bogota'`
- Ambos endpoints `/internal/*` requieren header `X-Internal-Token` (variable `INTERNAL_TOKEN` en config.py)

## Estructura de archivos

```
ph_saas/
├── main.py
├── config.py
├── database.py
├── scheduler.py
├── dependencies.py          ← get_current_user, require_role
├── middleware/
│   └── tenant.py            ← CRÍTICO: aislamiento tenant + verificación suscripción
├── models/
│   ├── conjunto.py
│   ├── usuario.py
│   ├── propiedad.py
│   ├── cuota.py
│   ├── pago.py
│   ├── suscripcion.py
│   ├── proceso_log.py
│   └── cuota_interes_log.py
├── schemas/
├── routers/
│   ├── auth.py
│   ├── conjuntos.py
│   ├── propiedades.py
│   ├── suscripciones.py
│   ├── views.py              ← pantallas HTML (login, SA, AD) — auth via cookies
│   ├── cuotas.py             ← Fase 2
│   ├── pagos.py              ← Fase 2
│   ├── cartera.py            ← Fase 3
│   ├── reportes.py           ← Fase 3
│   └── internal.py           ← /internal/generar-cuotas y /internal/calcular-intereses
├── services/
│   ├── cuota_service.py      ← Fase 2
│   ├── pago_service.py       ← Fase 2
│   ├── cartera_service.py    ← Fase 3
│   ├── pdf_service.py        ← Fase 3
│   ├── whatsapp_service.py   ← Fase 4
│   └── suscripcion_service.py
├── templates/               ← Jinja2 views (Fase 1) + HTML para PDFs WeasyPrint (Fase 3)
│   ├── base.html             ← layout sidebar Tailwind + Alpine.js
│   ├── login.html
│   ├── sa/                   ← vistas superadmin
│   │   ├── conjuntos.html
│   │   └── suscripciones.html
│   ├── app/                  ← vistas administrador
│   │   ├── propiedades.html
│   │   ├── usuarios.html
│   │   └── configuracion.html
│   └── pdf/                  ← Fase 3: paz_y_salvo.html, estado_cuenta.html
└── static/
```

## Servicios externos

| Servicio | Uso | Costo |
|---|---|---|
| Supabase | BD + Auth | Gratis hasta 500MB |
| Railway | Hosting | Gratis 500h/mes, luego ~$5/mes |
| Twilio | WhatsApp | Sandbox gratis, ~$0.005/msg producción |
| cron-job.org | Triggers automáticos | Gratuito |

## Deudas técnicas documentadas (Fase futura)

- Activar RLS de PostgreSQL (modelo ya compatible)
- 2FA para SuperAdmin (Supabase Auth lo soporta sin cambios de código)
- `saldo_a_favor_detalle` para pagos masivos (múltiples cuotas en una operación)
- Cron dinámico por conjunto usando `dia_generacion_cuota`
- Integración Wompi para cobro automático SaaS (+10 conjuntos)
