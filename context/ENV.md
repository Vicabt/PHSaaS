# ENV.md
> Lista completa de variables de entorno del proyecto.
> Copiar como `.env` en desarrollo y configurar en Railway para producción.
> Nunca subir `.env` a GitHub — agregar al `.gitignore`.

---

## .env.example

```env
# ─── SUPABASE ───────────────────────────────────────────────
SUPABASE_URL=https://xxxxxxxxxxxx.supabase.co
SUPABASE_ANON_KEY=eyJhbGci...
SUPABASE_SERVICE_ROLE_KEY=eyJhbGci...   # Solo para operaciones admin en backend

# ─── BASE DE DATOS ──────────────────────────────────────────
DATABASE_URL=postgresql://postgres:[PASSWORD]@db.xxxxxxxxxxxx.supabase.co:5432/postgres

# ─── AUTENTICACIÓN ──────────────────────────────────────────
JWT_SECRET=tu_jwt_secret_de_supabase     # Se obtiene en Supabase → Settings → API
SUPERADMIN_EMAIL=tu@email.com            # Email del superadmin en Supabase Auth

# ─── SEGURIDAD INTERNA ──────────────────────────────────────
INTERNAL_TOKEN=un_secreto_largo_y_aleatorio_minimo_32_chars
# Usado en header X-Internal-Token para endpoints /internal/*
# Generar con: python -c "import secrets; print(secrets.token_hex(32))"

# ─── TWILIO (WhatsApp) ──────────────────────────────────────
TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_AUTH_TOKEN=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_WHATSAPP_FROM=whatsapp:+14155238886   # Sandbox: este número. Producción: tu número registrado

# ─── ENTORNO ────────────────────────────────────────────────
ENVIRONMENT=development     # development | production
DEBUG=true                  # false en producción

# ─── APLICACIÓN ─────────────────────────────────────────────
APP_NAME=PH SaaS
APP_URL=http://localhost:8000     # En producción: https://tu-app.railway.app
TIMEZONE=America/Bogota
```

---

## Notas de configuración

### Supabase
- `SUPABASE_URL` y `SUPABASE_ANON_KEY`: Supabase → Project Settings → API
- `SUPABASE_SERVICE_ROLE_KEY`: mismo lugar, usar solo en backend nunca en frontend
- `DATABASE_URL`: Supabase → Project Settings → Database → Connection string (URI)

### INTERNAL_TOKEN
Generar un valor aleatorio seguro:
```bash
python -c "import secrets; print(secrets.token_hex(32))"
```
Configurar el mismo valor en Railway (variables de entorno) y en cron-job.org (header de las llamadas).

### Twilio sandbox (pruebas)
1. Crear cuenta en twilio.com
2. Activar sandbox de WhatsApp en Twilio Console
3. Usar `whatsapp:+14155238886` como número de origen
4. Los destinatarios deben enviar un mensaje al sandbox primero para activarse

### Railway
Agregar todas las variables en Railway → tu proyecto → Variables. No usar `.env` en producción.

---

## .gitignore mínimo

```
.env
.env.local
__pycache__/
*.pyc
.venv/
venv/
*.egg-info/
.DS_Store
```
