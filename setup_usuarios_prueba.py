"""
setup_usuarios_prueba.py
Crea (o verifica) todos los usuarios de prueba para revisar los templates del panel.
Idempotente: si el usuario ya existe, solo confirma.

Ejecutar: python setup_usuarios_prueba.py

Usuarios creados en "Conjunto de Prueba":
  admin.prueba@phsaas.com    / AdminPrueba2026$    → Administrador
  contador.prueba@phsaas.com / ContadorPrueba2026$ → Contador
  porteria.prueba@phsaas.com / PorteriaPrueba2026$ → Porteria
"""
from dotenv import load_dotenv
load_dotenv(".env")

from supabase import create_client
from sqlalchemy import create_engine, text
import os, uuid

SUPABASE_URL = os.getenv("SUPABASE_URL")
SERVICE_KEY  = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
DATABASE_URL = os.getenv("DATABASE_URL")

supabase = create_client(SUPABASE_URL, SERVICE_KEY)
engine   = create_engine(DATABASE_URL)

CONJUNTO_NOMBRE = "Conjunto de Prueba"

USUARIOS = [
    {
        "email":    "admin.prueba@phsaas.com",
        "password": "AdminPrueba2026$",
        "nombre":   "Admin",
        "apellido": "Prueba",
        "rol":      "Administrador",
    },
    {
        "email":    "contador.prueba@phsaas.com",
        "password": "ContadorPrueba2026$",
        "nombre":   "Contador",
        "apellido": "Prueba",
        "rol":      "Contador",
    },
    {
        "email":    "porteria.prueba@phsaas.com",
        "password": "PorteriaPrueba2026$",
        "nombre":   "Porteria",
        "apellido": "Prueba",
        "rol":      "Porteria",
    },
]


def get_or_create_supabase_user(email, password, nombre):
    """Crea el usuario en Supabase Auth o recupera su UUID si ya existe."""
    try:
        resp = supabase.auth.admin.create_user({
            "email": email,
            "password": password,
            "email_confirm": True,
        })
        uid = resp.user.id
        print(f"  ✅ Auth creado: {uid}")
        return uuid.UUID(str(uid))
    except Exception as e:
        if "already" in str(e).lower() or "exists" in str(e).lower():
            users = supabase.auth.admin.list_users()
            lst = users if isinstance(users, list) else getattr(users, "users", [])
            for u in lst:
                if u.email == email:
                    print(f"  ⚠️  Auth ya existía: {u.id}")
                    return uuid.UUID(str(u.id))
        print(f"  ❌ Error Auth: {e}")
        return None


def setup_usuario(conn, auth_uuid, email, nombre, apellido, rol, conjunto_id):
    # ── usuario en tabla local ────────────────────────────────────────────────
    existing = conn.execute(
        text("SELECT id FROM usuario WHERE id = :uid"), {"uid": auth_uuid}
    ).fetchone()
    if existing:
        print(f"  ⚠️  Usuario BD ya existía")
    else:
        conn.execute(text("""
            INSERT INTO usuario (id, nombre, apellido, correo, is_deleted, created_at)
            VALUES (:id, :nombre, :apellido, :correo, false, now())
        """), {"id": auth_uuid, "nombre": nombre, "apellido": apellido, "correo": email})
        print(f"  ✅ Usuario BD creado")

    # ── rol en el conjunto ────────────────────────────────────────────────────
    uc = conn.execute(
        text("""
            SELECT id FROM usuario_conjunto
            WHERE usuario_id = :uid AND conjunto_id = :cid AND is_deleted = false
        """),
        {"uid": auth_uuid, "cid": conjunto_id},
    ).fetchone()
    if uc:
        print(f"  ⚠️  Rol '{rol}' ya asignado")
    else:
        conn.execute(text("""
            INSERT INTO usuario_conjunto (id, usuario_id, conjunto_id, rol, is_deleted, created_at)
            VALUES (gen_random_uuid(), :uid, :cid, :rol, false, now())
        """), {"uid": auth_uuid, "cid": conjunto_id, "rol": rol})
        print(f"  ✅ Rol '{rol}' asignado")


# ── Main ──────────────────────────────────────────────────────────────────────
print("=" * 55)
print("Setup Usuarios de Prueba")
print("=" * 55)

with engine.begin() as conn:
    # Obtener o crear el Conjunto de Prueba
    row = conn.execute(
        text("SELECT id FROM conjunto WHERE nombre = :n AND is_deleted = false"),
        {"n": CONJUNTO_NOMBRE},
    ).fetchone()

    if row:
        conjunto_id = row[0]
        print(f"\n⚠️  Conjunto ya existía: {CONJUNTO_NOMBRE} ({conjunto_id})")
    else:
        conjunto_id = uuid.uuid4()
        conn.execute(text("""
            INSERT INTO conjunto (id, nombre, direccion, ciudad, is_deleted, created_at)
            VALUES (:id, :nombre, 'Calle 123 # 45-67', 'Bogotá', false, now())
        """), {"id": conjunto_id, "nombre": CONJUNTO_NOMBRE})
        print(f"\n✅ Conjunto creado: {CONJUNTO_NOMBRE} ({conjunto_id})")

    # Suscripción activa
    sus = conn.execute(
        text("SELECT id FROM suscripcion_saas WHERE conjunto_id = :cid"),
        {"cid": conjunto_id},
    ).fetchone()
    if sus:
        # Asegurar que esté Activo
        conn.execute(
            text("UPDATE suscripcion_saas SET estado = 'Activo', fecha_vencimiento = '2027-12-31', updated_at = now() WHERE conjunto_id = :cid"),
            {"cid": conjunto_id},
        )
        print(f"⚠️  Suscripción ya existía → confirmada Activo hasta 2027-12-31")
    else:
        conn.execute(text("""
            INSERT INTO suscripcion_saas (id, conjunto_id, estado, fecha_vencimiento, valor_mensual, created_at, updated_at)
            VALUES (gen_random_uuid(), :cid, 'Activo', '2027-12-31', 0, now(), now())
        """), {"cid": conjunto_id})
        print(f"✅ Suscripción creada (Activo hasta 2027-12-31)")

    # Configuracion del conjunto (si no existe)
    cfg = conn.execute(
        text("SELECT conjunto_id FROM configuracion_conjunto WHERE conjunto_id = :cid"),
        {"cid": conjunto_id},
    ).fetchone()
    if not cfg:
        conn.execute(text("""
            INSERT INTO configuracion_conjunto
              (conjunto_id, valor_cuota_estandar, dia_generacion_cuota,
               dia_notificacion_mora, tasa_interes_mora, permitir_interes,
               created_at, updated_at)
            VALUES (:cid, 250000, 1, 5, 2.00, true, now(), now())
        """), {"cid": conjunto_id})
        print("✅ Configuración creada (cuota $250.000, tasa mora 2%)")
    else:
        print("⚠️  Configuración ya existía")

    # Propiedades de ejemplo (si no existen)
    existing_props = conn.execute(
        text("SELECT COUNT(*) FROM propiedad WHERE conjunto_id = :cid AND is_deleted = false"),
        {"cid": conjunto_id},
    ).scalar()
    if existing_props == 0:
        for apt in ["101", "102", "201", "202", "301"]:
            conn.execute(text("""
                INSERT INTO propiedad (id, conjunto_id, numero_apartamento, estado, is_deleted, created_at)
                VALUES (gen_random_uuid(), :cid, :apt, 'Activo', false, now())
            """), {"cid": conjunto_id, "apt": apt})
        print("✅ 5 propiedades de ejemplo creadas (101, 102, 201, 202, 301)")
    else:
        print(f"⚠️  Ya existen {existing_props} propiedad(es)")

    # Crear cada usuario
    for u in USUARIOS:
        print(f"\n── {u['rol']}: {u['email']}")
        auth_uuid = get_or_create_supabase_user(u["email"], u["password"], u["nombre"])
        if auth_uuid:
            setup_usuario(conn, auth_uuid, u["email"], u["nombre"], u["apellido"], u["rol"], conjunto_id)

# ── Resumen final ─────────────────────────────────────────────────────────────
print(f"""
{'=' * 55}
✅ Setup completo — Usuarios de prueba
{'=' * 55}
Conjunto : {CONJUNTO_NOMBRE}

  Rol            Email                          Password
  ─────────────────────────────────────────────────────────
  SuperAdmin     vccompany011@email.com         Vc92985315$%
  Administrador  admin.prueba@phsaas.com        AdminPrueba2026$
  Contador       contador.prueba@phsaas.com     ContadorPrueba2026$
  Porteria       porteria.prueba@phsaas.com     PorteriaPrueba2026$

URL del panel: http://localhost:8000
{'=' * 55}
""")
