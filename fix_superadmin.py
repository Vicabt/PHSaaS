"""
fix_superadmin.py — Lista todos los usuarios y corrige la contraseña del superadmin.
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

# Listar con paginación
print("=== Listando usuarios (paginado) ===")
try:
    resp = supabase.auth.admin.list_users(page=1, per_page=50)
    # supabase-py v2 puede devolver objetos distintos
    print(f"Tipo de respuesta: {type(resp)}")
    print(f"Atributos: {dir(resp)}")
    if hasattr(resp, 'users'):
        users = resp.users
    elif isinstance(resp, list):
        users = resp
    else:
        users = list(resp)
    print(f"Total usuarios: {len(users)}")
    for u in users:
        print(f"  - {getattr(u, 'email', '?')} | id={getattr(u, 'id', '?')} | confirmed={bool(getattr(u, 'email_confirmed_at', None))}")
except Exception as e:
    print(f"Error: {e}")

# Buscar usuario por email y actualizar contraseña
print(f"\n=== Actualizar contraseña de {EMAIL} ===")
try:
    # getUserById no existe directo, pero podemos hacer un reset via admin
    # Primero buscamos el ID
    for u in users:
        if getattr(u, 'email', '') == EMAIL:
            uid = u.id
            print(f"Encontrado id={uid}")
            # Actualizar contraseña via admin
            result = supabase.auth.admin.update_user_by_id(
                uid,
                {"password": PASSWORD}
            )
            print(f"✅ Contraseña actualizada: {result.user.email}")
            
            # Intentar sign in ahora
            anon = create_client(SUPABASE_URL, os.getenv('SUPABASE_ANON_KEY'))
            r2 = anon.auth.sign_in_with_password({"email": EMAIL, "password": PASSWORD})
            print(f"✅ Sign in OK! token={r2.session.access_token[:40]}...")
            print(f"   app_metadata: {r2.user.app_metadata}")
            break
    else:
        print(f"Usuario {EMAIL} no encontrado en la lista")
        # Intentar crear de nuevo
        print("Creando usuario...")
        new_user = supabase.auth.admin.create_user({
            "email": EMAIL,
            "password": PASSWORD,
            "email_confirm": True,
            "app_metadata": {"role": "superadmin"}
        })
        print(f"✅ Creado: id={new_user.user.id}")
        
        # Sign in
        anon = create_client(SUPABASE_URL, os.getenv('SUPABASE_ANON_KEY'))
        r2 = anon.auth.sign_in_with_password({"email": EMAIL, "password": PASSWORD})
        print(f"✅ Sign in OK! token={r2.session.access_token[:40]}...")
except Exception as e:
    print(f"Error: {type(e).__name__}: {e}")
