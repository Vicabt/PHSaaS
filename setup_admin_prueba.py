"""
setup_admin_prueba.py — Crea un usuario Administrador de conjunto para pruebas.
Ejecutar una sola vez: python setup_admin_prueba.py
"""
from dotenv import load_dotenv
load_dotenv('.env')

from supabase import create_client
from sqlalchemy import create_engine, text
import os, uuid

SUPABASE_URL = os.getenv('SUPABASE_URL')
SERVICE_KEY  = os.getenv('SUPABASE_SERVICE_ROLE_KEY')
DATABASE_URL = os.getenv('DATABASE_URL')

EMAIL    = "admin.prueba@phsaas.com"
PASSWORD = "AdminPrueba2026$"
NOMBRE   = "Admin Prueba"

supabase = create_client(SUPABASE_URL, SERVICE_KEY)
engine   = create_engine(DATABASE_URL)

print("=== Setup Admin de Prueba ===\n")

# ── 1. Crear usuario en Supabase Auth ─────────────────────────────────────────
auth_id = None
try:
    resp = supabase.auth.admin.create_user({
        "email": EMAIL,
        "password": PASSWORD,
        "email_confirm": True,
    })
    auth_id = resp.user.id
    print(f"✅ Auth creado: {auth_id}")
except Exception as e:
    if "already" in str(e).lower() or "exists" in str(e).lower():
        # Buscar el UUID existente
        users = supabase.auth.admin.list_users()
        lst = users if isinstance(users, list) else getattr(users, 'users', [])
        for u in lst:
            if u.email == EMAIL:
                auth_id = u.id
                break
        print(f"⚠️  Auth ya existía: {auth_id}")
    else:
        print(f"❌ Error Auth: {e}")
        exit(1)

if not auth_id:
    print("❌ No se pudo obtener el auth_id")
    exit(1)

auth_uuid = uuid.UUID(str(auth_id))

with engine.begin() as conn:

    # ── 2. Crear conjunto ─────────────────────────────────────────────────────
    conjunto_id = uuid.uuid4()
    existing = conn.execute(
        text("SELECT id FROM conjunto WHERE nombre = 'Conjunto de Prueba' AND is_deleted = false")
    ).fetchone()

    if existing:
        conjunto_id = existing[0]
        print(f"⚠️  Conjunto ya existía: {conjunto_id}")
    else:
        conn.execute(text("""
            INSERT INTO conjunto (id, nombre, direccion, ciudad, is_deleted, created_at)
            VALUES (:id, :nombre, :dir, :ciudad, false, now())
        """), {"id": conjunto_id, "nombre": "Conjunto de Prueba",
               "dir": "Calle 123 # 45-67", "ciudad": "Bogotá"})
        print(f"✅ Conjunto creado: {conjunto_id}")

    # ── 3. Crear suscripción activa ───────────────────────────────────────────
    sus = conn.execute(
        text("SELECT id FROM suscripcion_saas WHERE conjunto_id = :cid"),
        {"cid": conjunto_id}
    ).fetchone()

    if sus:
        print(f"⚠️  Suscripción ya existía")
    else:
        conn.execute(text("""
            INSERT INTO suscripcion_saas (id, conjunto_id, estado, fecha_vencimiento, valor_mensual, created_at, updated_at)
            VALUES (gen_random_uuid(), :cid, 'Activo', '2027-12-31', 0, now(), now())
        """), {"cid": conjunto_id})
        print(f"✅ Suscripción creada")

    # ── 4. Crear registro en tabla usuario ────────────────────────────────────
    usr = conn.execute(
        text("SELECT id FROM usuario WHERE id = :uid"),
        {"uid": auth_uuid}
    ).fetchone()

    if usr:
        print(f"⚠️  Usuario BD ya existía")
    else:
        conn.execute(text("""
            INSERT INTO usuario (id, nombre, correo, is_deleted, created_at)
            VALUES (:id, :nombre, :correo, false, now())
        """), {"id": auth_uuid, "nombre": NOMBRE, "correo": EMAIL})
        print(f"✅ Usuario BD creado")

    # ── 5. Asignar rol Administrador al conjunto ──────────────────────────────
    uc = conn.execute(
        text("SELECT id FROM usuario_conjunto WHERE usuario_id = :uid AND conjunto_id = :cid AND is_deleted = false"),
        {"uid": auth_uuid, "cid": conjunto_id}
    ).fetchone()

    if uc:
        print(f"⚠️  Rol ya asignado")
    else:
        conn.execute(text("""
            INSERT INTO usuario_conjunto (id, usuario_id, conjunto_id, rol, is_deleted, created_at)
            VALUES (gen_random_uuid(), :uid, :cid, 'Administrador', false, now())
        """), {"uid": auth_uuid, "cid": conjunto_id})
        print(f"✅ Rol Administrador asignado")

print(f"""
══════════════════════════════════════
✅ Setup completo. Credenciales:
   Email:    {EMAIL}
   Password: {PASSWORD}
   Conjunto: Conjunto de Prueba
══════════════════════════════════════
""")
