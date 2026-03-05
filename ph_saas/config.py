"""
config.py — Configuración global del proyecto.
Lee variables de entorno desde .env (desarrollo) o variables del sistema (producción).
"""

import pytz
from pydantic_settings import BaseSettings


# Zona horaria del sistema — usar en todo timestamp
BOGOTA_TZ = pytz.timezone("America/Bogota")


class Settings(BaseSettings):
    # Supabase
    SUPABASE_URL: str
    SUPABASE_ANON_KEY: str
    SUPABASE_SERVICE_ROLE_KEY: str

    # Base de datos
    DATABASE_URL: str

    # Autenticación
    # OJO: JWT_SECRET es el "JWT Secret" de Supabase → Settings → API → JWT Settings
    # NO es el anon key. Es un string aleatorio largo.
    JWT_SECRET: str
    SUPERADMIN_EMAIL: str

    # Seguridad interna — endpoints /internal/*
    INTERNAL_TOKEN: str

    # Twilio (WhatsApp) — opcionales, requeridos en Fase 4
    TWILIO_ACCOUNT_SID: str = ""
    TWILIO_AUTH_TOKEN: str = ""
    TWILIO_WHATSAPP_FROM: str = "whatsapp:+14155238886"

    # Entorno
    ENVIRONMENT: str = "development"
    DEBUG: bool = True

    # Aplicación
    APP_NAME: str = "PH SaaS"
    APP_URL: str = "http://localhost:8000"
    TIMEZONE: str = "America/Bogota"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
