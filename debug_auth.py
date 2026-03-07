"""
debug_auth.py — Diagnóstico del superadmin en Supabase Auth.
"""
from dotenv import load_dotenv
load_dotenv('.env')

from supabase import create_client
import os

SUPABASE_URL = os.getenv('SUPABASE_URL')
ANON_KEY = os.getenv('SUPABASE_ANON_KEY')
SERVICE_KEY = os.getenv('SUPABASE_SERVICE_ROLE_KEY')
EMAIL = "vccompany011@email.com"

print("=== Diagnóstico Supabase Auth ===\n")

# 1. Intentar con contraseñas posibles
supabase_anon = create_client(SUPABASE_URL, ANON_KEY)

passwords_a_probar = [
    "Vc92985315$%",
    "Vc92985315%",
    "Vc92985315%$",
    "Vc92985315",
]

for pwd in passwords_a_probar:
    try:
        r = supabase_anon.auth.sign_in_with_password({"email": EMAIL, "password": pwd})
        print(f"✅ Login OK con contraseña: {pwd!r}")
        print(f"   user id: {r.user.id}")
        print(f"   app_metadata: {r.user.app_metadata}")
        break
    except Exception as e:
        print(f"❌ Falló con {pwd!r}: {e}")

# 2. Verificar si el usuario existe via admin API
print("\n=== Admin API — buscar usuario ===")
try:
    supabase_admin = create_client(SUPABASE_URL, SERVICE_KEY)
    # Listar usuarios
    resp = supabase_admin.auth.admin.list_users()
    users = resp if isinstance(resp, list) else getattr(resp, 'users', [])
    found = [u for u in users if getattr(u, 'email', '') == EMAIL]
    if found:
        u = found[0]
        print(f"✅ Usuario encontrado:")
        print(f"   id: {u.id}")
        print(f"   email: {u.email}")
        print(f"   email_confirmed: {u.email_confirmed_at}")
        print(f"   app_metadata: {u.app_metadata}")
        print(f"   user_metadata: {u.user_metadata}")
    else:
        print(f"❌ Usuario {EMAIL!r} NO existe en Supabase Auth")
        print(f"   Total usuarios: {len(users)}")
except Exception as e:
    print(f"Error admin API: {e}")
