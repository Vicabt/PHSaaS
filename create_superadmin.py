"""
create_superadmin.py — Crea el usuario superadmin en Supabase Auth con app_metadata.
"""
from dotenv import load_dotenv
load_dotenv('.env')

from supabase import create_client
import os

SUPABASE_URL = os.getenv('SUPABASE_URL')
SERVICE_KEY = os.getenv('SUPABASE_SERVICE_ROLE_KEY')
EMAIL = "vccompany011@email.com"
PASSWORD = "Vc92985315$%"

supabase = create_client(SUPABASE_URL, SERVICE_KEY)

print(f"Creando superadmin: {EMAIL}")

# Ver usuario existente primero
try:
    resp = supabase.auth.admin.list_users()
    users = resp if isinstance(resp, list) else getattr(resp, 'users', [])
    print(f"Usuarios existentes: {[(u.email, u.id) for u in users]}")
except Exception as e:
    print(f"Error listando: {e}")

# Crear superadmin
try:
    user = supabase.auth.admin.create_user({
        "email": EMAIL,
        "password": PASSWORD,
        "email_confirm": True,
        "app_metadata": {
            "role": "superadmin"
        }
    })
    print(f"\n✅ Superadmin creado exitosamente:")
    print(f"   id: {user.user.id}")
    print(f"   email: {user.user.email}")
    print(f"   app_metadata: {user.user.app_metadata}")
    print(f"   email_confirmed: {user.user.email_confirmed_at}")
except Exception as e:
    print(f"\n❌ Error al crear: {e}")
    # Si ya existe, intentar actualizar
    if "already" in str(e).lower() or "exists" in str(e).lower():
        print("El usuario ya existe. Intentando actualizar metadata...")

print("\nListo.")
