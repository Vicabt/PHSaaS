# ARCHITECTURE.md
> Archivo de contexto para desarrollo. Leer antes de escribir cualquier código.
> Extraído de PROYECTO_PH_SAAS.md v2.5

---

## Stack tecnológico

| Capa | Tecnología |
|---|---|
| Backend | Python 3.12 + FastAPI |
| Base de datos | PostgreSQL via Supabase |
| Frontend | HTML + Tailwind CSS + HTMX |
| Autenticación | Supabase Auth (JWT) |
| PDFs | WeasyPrint |
| Notificaciones | Twilio (WhatsApp) |
| Jobs automáticos | APScheduler + cron-job.org |
| Hosting | Railway |

## Multi-tenant

- Modelo: Shared Database + filtros por `conjunto_id` en código Python
- Cada tabla funcional tiene `conjunto_id UUID NOT NULL`
- El aislamiento se hace en `middleware/tenant.py`, NO en RLS de PostgreSQL (Fase 1)

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
│   ├── cuotas.py
│   ├── pagos.py
│   ├── cartera.py
│   ├── reportes.py
│   ├── suscripciones.py
│   └── internal.py          ← /internal/generar-cuotas y /internal/calcular-intereses
├── services/
│   ├── cuota_service.py
│   ├── pago_service.py
│   ├── cartera_service.py
│   ├── pdf_service.py
│   ├── whatsapp_service.py
│   └── suscripcion_service.py
├── templates/               ← HTML para PDFs (WeasyPrint)
│   ├── paz_y_salvo.html
│   ├── estado_cuenta.html
│   └── cartera.html
├── static/
└── pages/                   ← HTML + HTMX del frontend
    ├── login.html
    ├── dashboard.html
    ├── propiedades.html
    ├── cuotas.html
    ├── pagos.html
    ├── reportes.html
    └── suscripciones.html
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
