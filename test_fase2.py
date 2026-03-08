"""
test_fase2.py - Prueba integral de Fase 2: Cuotas y Pagos.

Estrategia:
  - Setup via SQLAlchemy directo (mismo patrón que create_superadmin.py):
    conjunto, suscripcion, configuracion, propiedad, usuario admin
  - Tests via HTTP con token del usuario admin (para /api/*) y
    X-Internal-Token (para /internal/*)
  - Cleanup completo al finalizar (try/finally)

Prerrequisitos:
  - Servidor en http://localhost:8000 (o ajustar BASE)
  - .env con credenciales válidas en V1.0/
  - Usuario superadmin existente

Ejecutar desde V1.0/:  python test_fase2.py
"""

import sys
import uuid
from datetime import date, datetime
from decimal import Decimal

import httpx
from dotenv import load_dotenv

load_dotenv(".env")

# ── Configurar Python path para importar ph_saas ──────────────────────────────
sys.path.insert(0, ".")

from ph_saas.config import settings, BOGOTA_TZ
from ph_saas.database import SessionLocal
from ph_saas.models.conjunto import Conjunto
from ph_saas.models.configuracion_conjunto import ConfiguracionConjunto
from ph_saas.models.propiedad import Propiedad
from ph_saas.models.suscripcion import SuscripcionSaaS
from ph_saas.models.usuario import Usuario
from ph_saas.models.usuario_conjunto import UsuarioConjunto

from supabase import create_client

# ── Constantes ─────────────────────────────────────────────────────────────────

BASE              = "http://localhost:8000"
SUPERADMIN_EMAIL  = "vccompany011@email.com"
SA_PASSWORD       = "Vc92985315$%"
_TEST_UID         = uuid.uuid4().hex[:6]
TEST_ADMIN_EMAIL  = f"test_admin_{_TEST_UID}@test.com"
TEST_ADMIN_PASS   = "TestPass123$"
TEST_PERIODO_1    = "2025-12"   # Periodo pasado — elegible para cálculo de intereses
TEST_PERIODO_2    = "2026-01"   # Segundo periodo para tests de saldo a favor
INTERNAL_TOKEN    = settings.INTERNAL_TOKEN
TIMEOUT           = 30.0

_supabase = create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_ROLE_KEY)

# ── IDs creados durante el test (para cleanup) ────────────────────────────────
_created_conjunto_id   : uuid.UUID | None = None
_created_propiedad_id  : uuid.UUID | None = None
_created_auth_user_id  : str | None       = None

# ── Helpers de output ─────────────────────────────────────────────────────────

def ok(msg):   print(f"  [OK]   {msg}")
def fail(msg): print(f"  [FAIL] {msg}")
def info(msg): print(f"  [INFO] {msg}")
def sep(title): print(f"\n{'='*60}\n{title}\n{'='*60}")

client = httpx.Client(timeout=TIMEOUT)
_fail_count = 0

def check(condition: bool, msg_ok: str, msg_fail: str):
    global _fail_count
    if condition:
        ok(msg_ok)
    else:
        fail(msg_fail)
        _fail_count += 1


# ══════════════════════════════════════════════════════════════════════════════
# SETUP: crear datos directamente en BD + Supabase Auth
# ══════════════════════════════════════════════════════════════════════════════

def setup_datos() -> tuple[uuid.UUID, uuid.UUID, str]:
    """
    Crea en BD: conjunto, suscripcion, configuracion, propiedad, usuario, usuario_conjunto.
    Crea en Supabase Auth: usuario admin con app_metadata.conjunto_id.
    Retorna (conjunto_id, propiedad_id, auth_user_id_str).
    """
    global _created_conjunto_id, _created_propiedad_id, _created_auth_user_id

    sep("SETUP — Creando datos de prueba directamente en BD")
    db = SessionLocal()
    auth_user_id_str = None

    try:
        # 1. Conjunto
        conjunto = Conjunto(
            nombre=f"Conjunto Fase2 Test {uuid.uuid4().hex[:6]}",
            nit="900-TEST-2",
            direccion="Calle Test 123",
            ciudad="Bogotá",
        )
        db.add(conjunto)
        db.flush()
        _created_conjunto_id = conjunto.id
        ok(f"Conjunto creado: {conjunto.id} — {conjunto.nombre}")

        # 2. Suscripción
        vencimiento = date(2026, 12, 31)
        sus = SuscripcionSaaS(
            conjunto_id=conjunto.id,
            estado="Activo",
            fecha_vencimiento=vencimiento,
            valor_mensual=Decimal("150000"),
        )
        db.add(sus)
        ok(f"Suscripcion: estado=Activo, vence={vencimiento}")

        # 3. Configuración
        config = ConfiguracionConjunto(
            conjunto_id=conjunto.id,
            valor_cuota_estandar=Decimal("500000.00"),
            tasa_interes_mora=Decimal("2.00"),
            permitir_interes=True,
            dia_generacion_cuota=1,
            dia_notificacion_mora=5,
        )
        db.add(config)
        ok("Configuracion: cuota=500000, tasa_mora=2%, permitir_interes=True")

        # 4. Propiedad
        propiedad = Propiedad(
            conjunto_id=conjunto.id,
            numero_apartamento="101",
            estado="Activo",
        )
        db.add(propiedad)
        db.flush()
        _created_propiedad_id = propiedad.id
        ok(f"Propiedad 101 creada: {propiedad.id}")

        # 5. Usuario admin en Supabase Auth
        info(f"Creando usuario admin en Supabase Auth: {TEST_ADMIN_EMAIL}")
        auth_resp = _supabase.auth.admin.create_user({
            "email": TEST_ADMIN_EMAIL,
            "password": TEST_ADMIN_PASS,
            "email_confirm": True,
            "app_metadata": {
                "conjunto_id": str(conjunto.id),
            },
        })
        auth_user = auth_resp.user
        auth_user_id_str = str(auth_user.id)
        _created_auth_user_id = auth_user_id_str
        ok(f"Usuario Supabase creado: {auth_user_id_str[:8]}...")

        # 6. Registro en tabla usuario
        usuario = Usuario(
            id=uuid.UUID(auth_user_id_str),
            nombre="Admin Test Fase2",
            correo=TEST_ADMIN_EMAIL,
            cedula=f"9{_TEST_UID}",
        )
        db.add(usuario)
        db.flush()
        ok(f"Registro usuario BD creado")

        # 7. Usuario_conjunto con rol Administrador
        uc = UsuarioConjunto(
            usuario_id=usuario.id,
            conjunto_id=conjunto.id,
            rol="Administrador",
        )
        db.add(uc)
        db.commit()
        ok("UsuarioConjunto rol=Administrador asignado")

        return conjunto.id, propiedad.id, auth_user_id_str

    except Exception as e:
        db.rollback()
        print(f"\n  [ERROR] Fallo en setup: {e}")
        raise
    finally:
        db.close()


def cleanup_datos(conjunto_id: uuid.UUID | None, auth_user_id: str | None):
    """Elimina todos los registros de prueba (hard delete en test data)."""
    sep("CLEANUP — Eliminando datos de prueba")
    db = SessionLocal()
    try:
        if conjunto_id:
            # Importar modelos necesarios para cleanup
            from ph_saas.models.cuota import Cuota
            from ph_saas.models.pago import Pago
            from ph_saas.models.pago_detalle import PagoDetalle
            from ph_saas.models.saldo_a_favor import SaldoAFavor
            from ph_saas.models.movimiento_contable import MovimientoContable
            from ph_saas.models.proceso_log import ProcesoLog
            from ph_saas.models.cuota_interes_log import CuotaInteresLog

            # Orden inverso de FK: primero hijos, luego padres
            cuotas = db.query(Cuota).filter(Cuota.conjunto_id == conjunto_id).all()
            cuota_ids = [c.id for c in cuotas]

            db.query(CuotaInteresLog).filter(CuotaInteresLog.conjunto_id == conjunto_id).delete()
            db.query(PagoDetalle).filter(PagoDetalle.cuota_id.in_(cuota_ids)).delete(synchronize_session=False)
            db.query(SaldoAFavor).filter(SaldoAFavor.conjunto_id == conjunto_id).delete()
            db.query(Pago).filter(Pago.conjunto_id == conjunto_id).delete()
            db.query(MovimientoContable).filter(MovimientoContable.conjunto_id == conjunto_id).delete()
            db.query(ProcesoLog).filter(ProcesoLog.conjunto_id == conjunto_id).delete()
            db.query(Cuota).filter(Cuota.conjunto_id == conjunto_id).delete()
            db.query(UsuarioConjunto).filter(UsuarioConjunto.conjunto_id == conjunto_id).delete()
            db.query(Propiedad).filter(Propiedad.conjunto_id == conjunto_id).delete()
            db.query(ConfiguracionConjunto).filter(ConfiguracionConjunto.conjunto_id == conjunto_id).delete()
            db.query(SuscripcionSaaS).filter(SuscripcionSaaS.conjunto_id == conjunto_id).delete()
            db.query(Conjunto).filter(Conjunto.id == conjunto_id).delete()
            db.commit()
            ok(f"Registros BD eliminados para conjunto {conjunto_id}")

        if auth_user_id:
            try:
                db.query(Usuario).filter(Usuario.id == uuid.UUID(auth_user_id)).delete()
                db.commit()
                _supabase.auth.admin.delete_user(auth_user_id)
                ok(f"Usuario Supabase Auth eliminado: {auth_user_id[:8]}...")
            except Exception as e:
                fail(f"Error eliminando usuario Auth: {e}")

    except Exception as e:
        db.rollback()
        fail(f"Error en cleanup: {e}")
    finally:
        db.close()


# ══════════════════════════════════════════════════════════════════════════════
# MAIN: ejecutar tests
# ══════════════════════════════════════════════════════════════════════════════

def run_tests(
    conjunto_id: uuid.UUID,
    propiedad_id: uuid.UUID,
    admin_token: str,
):
    ADM_HDR = {"Authorization": f"Bearer {admin_token}"}
    INT_HDR = {"X-Internal-Token": INTERNAL_TOKEN}
    C_ID = str(conjunto_id)
    P_ID = str(propiedad_id)

    # ── 1. HEALTH ─────────────────────────────────────────────────────────────
    sep("1. HEALTH")
    r = client.get(f"{BASE}/health")
    check(r.status_code == 200 and r.json().get("status") == "ok",
          f"GET /health → {r.json()}",
          f"GET /health → {r.status_code}: {r.text}")

    # ── 2. AUTH ENDPOINTS ─────────────────────────────────────────────────────
    sep("2. AUTH — Endpoints sin token")
    r = client.get(f"{BASE}/api/cuotas")
    check(r.status_code == 401, "GET /api/cuotas sin token → 401", f"Esperaba 401, recibió {r.status_code}")

    r = client.post(f"{BASE}/api/pagos", json={})
    check(r.status_code == 401, "POST /api/pagos sin token → 401", f"Esperaba 401, recibió {r.status_code}")

    # ── 3. CUOTAS — GENERACIÓN ────────────────────────────────────────────────
    sep("3. CUOTAS — Generación")

    # Validación de schema: periodo con formato incorrecto
    r = client.post(f"{BASE}/api/cuotas/generar", json={"periodo": "12-2025"}, headers=ADM_HDR)
    check(r.status_code == 422, "POST /api/cuotas/generar (periodo inválido) → 422", f"Esperaba 422, recibió {r.status_code}: {r.text}")

    # Generar cuotas período 1
    r = client.post(f"{BASE}/api/cuotas/generar", json={"periodo": TEST_PERIODO_1}, headers=ADM_HDR)
    print(f"  POST /api/cuotas/generar ({TEST_PERIODO_1}) → {r.status_code}")
    check(r.status_code == 201, f"Cuotas generadas para {TEST_PERIODO_1}", f"ERROR: {r.text}")
    if r.status_code != 201:
        print("  [ABORT  Test abortado — no se pudo generar cuotas]")
        return

    cuotas_generadas = r.json()
    check(len(cuotas_generadas) == 1, f"1 cuota generada (propiedad 101)", f"Se esperaba 1, se obtuvieron {len(cuotas_generadas)}")

    cuota1 = cuotas_generadas[0]
    CUOTA1_ID = cuota1["id"]
    check(cuota1["estado"] == "Pendiente",            f"Cuota estado=Pendiente",    f"Estado={cuota1['estado']}")
    check(cuota1["valor_base"] == "500000.00",         f"valor_base=500000.00",       f"valor_base={cuota1['valor_base']}")
    check(cuota1["interes_generado"] == "0.00",        f"interes_generado=0.00",      f"interes={cuota1['interes_generado']}")
    check(cuota1["fecha_vencimiento"] == "2025-12-31", f"fecha_vencimiento=2025-12-31", f"vencimiento={cuota1['fecha_vencimiento']}")

    # Idempotencia: generar el mismo periodo dos veces → 400
    r = client.post(f"{BASE}/api/cuotas/generar", json={"periodo": TEST_PERIODO_1}, headers=ADM_HDR)
    check(r.status_code == 400, f"POST /api/cuotas/generar ({TEST_PERIODO_1}) segunda vez → 400 (idempotencia)", f"Esperaba 400, recibió {r.status_code}")

    # Generar período 2 (para tests de saldo a favor después)
    r = client.post(f"{BASE}/api/cuotas/generar", json={"periodo": TEST_PERIODO_2}, headers=ADM_HDR)
    check(r.status_code == 201, f"Cuotas generadas {TEST_PERIODO_2}", f"ERROR {TEST_PERIODO_2}: {r.text}")
    cuotas_2 = r.json()
    CUOTA2_ID = cuotas_2[0]["id"] if cuotas_2 else None

    # ── 4. CUOTAS — LISTADO Y DETALLE ─────────────────────────────────────────
    sep("4. CUOTAS — Listado y detalle")

    r = client.get(f"{BASE}/api/cuotas", headers=ADM_HDR)
    check(r.status_code == 200, f"GET /api/cuotas → 200 ({len(r.json())} cuotas)", f"ERROR: {r.text}")
    check(len(r.json()) == 2, "2 cuotas total (una por cada periodo)", f"Esperaba 2, obtuvo {len(r.json())}")

    r = client.get(f"{BASE}/api/cuotas?periodo={TEST_PERIODO_1}", headers=ADM_HDR)
    check(r.status_code == 200 and len(r.json()) == 1,
          f"GET /api/cuotas?periodo={TEST_PERIODO_1} → 1 cuota",
          f"ERROR: {r.status_code} {r.text}")

    r = client.get(f"{BASE}/api/cuotas/{CUOTA1_ID}", headers=ADM_HDR)
    check(r.status_code == 200, f"GET /api/cuotas/{{id}} → 200", f"ERROR: {r.text}")
    det = r.json()
    check("saldo_pendiente" in det and det["saldo_pendiente"] == "500000.00",
          f"saldo_pendiente=500000.00 en detalle",
          f"saldo_pendiente={det.get('saldo_pendiente')}")

    r = client.get(f"{BASE}/api/cuotas/00000000-0000-0000-0000-000000000000", headers=ADM_HDR)
    check(r.status_code == 404, "GET cuota inexistente → 404", f"Esperaba 404, recibió {r.status_code}")

    r = client.get(f"{BASE}/api/cuotas/propiedad/{P_ID}", headers=ADM_HDR)
    check(r.status_code == 200, f"GET /api/cuotas/propiedad/{{id}} → 200", f"ERROR: {r.text}")
    check(len(r.json()) == 2, "2 cuotas para la propiedad", f"Esperaba 2, obtuvo {len(r.json())}")

    # ── 5. PAGOS — PAGO PARCIAL ───────────────────────────────────────────────
    sep("5. PAGOS — Pago parcial")

    pago1_body = {
        "propiedad_id": P_ID,
        "fecha_pago": str(date.today()),
        "valor_total": "200000",
        "metodo_pago": "Efectivo",
        "detalles": [
            {"cuota_id": CUOTA1_ID, "monto_aplicado": "200000"}
        ],
    }
    r = client.post(f"{BASE}/api/pagos", json=pago1_body, headers=ADM_HDR)
    check(r.status_code == 201, "POST /api/pagos (abono parcial 200k) → 201", f"ERROR: {r.text}")
    if r.status_code != 201:
        print("  [ABORT] No se pudo registrar pago")
        return
    pago1 = r.json()
    PAGO1_ID = pago1["id"]
    check(len(pago1["detalles"]) == 1, "Pago tiene 1 detalle", f"Detalles: {len(pago1['detalles'])}")

    # Verificar que cuota cambió a Parcial
    r = client.get(f"{BASE}/api/cuotas/{CUOTA1_ID}", headers=ADM_HDR)
    det = r.json()
    check(det["estado"] == "Parcial", "Cuota cambió a estado=Parcial", f"Estado={det['estado']}")
    check(det["saldo_pendiente"] == "300000.00",
          "saldo_pendiente=300000.00 tras pago parcial",
          f"saldo_pendiente={det.get('saldo_pendiente')}")

    # ── 6. PAGOS — LISTADO Y DETALLE ─────────────────────────────────────────
    sep("6. PAGOS — Listado y detalle")

    r = client.get(f"{BASE}/api/pagos", headers=ADM_HDR)
    check(r.status_code == 200, f"GET /api/pagos → 200 ({len(r.json())} pagos)", f"ERROR: {r.text}")

    r = client.get(f"{BASE}/api/pagos/{PAGO1_ID}", headers=ADM_HDR)
    check(r.status_code == 200, f"GET /api/pagos/{{id}} → 200", f"ERROR: {r.text}")
    det_pago = r.json()
    check(det_pago["valor_total"] == "200000.00", "valor_total=200000.00", f"valor_total={det_pago['valor_total']}")
    check(len(det_pago["detalles"]) == 1, "1 detalle en pago", f"Detalles: {len(det_pago['detalles'])}")
    detalle = det_pago["detalles"][0]
    check(detalle["monto_a_capital"] == "200000.00",
          "monto_a_capital=200000.00 (sin interes pendiente)",
          f"monto_a_capital={detalle['monto_a_capital']}")
    check(detalle["monto_a_interes"] == "0.00",
          "monto_a_interes=0.00 (cuota sin interes)",
          f"monto_a_interes={detalle['monto_a_interes']}")

    r = client.get(f"{BASE}/api/pagos/00000000-0000-0000-0000-000000000000", headers=ADM_HDR)
    check(r.status_code == 404, "GET pago inexistente → 404", f"Esperaba 404, recibió {r.status_code}")

    # ── 7. PAGOS — VALIDACIONES ───────────────────────────────────────────────
    sep("7. PAGOS — Validaciones de negocio")

    # Monto negativo
    r = client.post(f"{BASE}/api/pagos", json={
        "propiedad_id": P_ID, "fecha_pago": str(date.today()),
        "valor_total": "-100", "metodo_pago": "Efectivo",
        "detalles": [{"cuota_id": CUOTA1_ID, "monto_aplicado": "-100"}],
    }, headers=ADM_HDR)
    check(r.status_code == 422, "POST /api/pagos (monto negativo) → 422", f"Esperaba 422, recibió {r.status_code}")

    # Monto excede deuda (saldo pendiente cuota1 = 300000)
    r = client.post(f"{BASE}/api/pagos", json={
        "propiedad_id": P_ID, "fecha_pago": str(date.today()),
        "valor_total": "500000", "metodo_pago": "Efectivo",
        "detalles": [{"cuota_id": CUOTA1_ID, "monto_aplicado": "500000"}],
    }, headers=ADM_HDR)
    check(r.status_code == 400, "POST /api/pagos (excede deuda) → 400", f"Esperaba 400, recibió {r.status_code}: {r.text}")

    # Sin detalles → 422
    r = client.post(f"{BASE}/api/pagos", json={
        "propiedad_id": P_ID, "fecha_pago": str(date.today()),
        "valor_total": "300000", "metodo_pago": "Efectivo", "detalles": [],
    }, headers=ADM_HDR)
    check(r.status_code == 422, "POST /api/pagos (sin detalles) → 422", f"Esperaba 422, recibió {r.status_code}")

    # ── 8. PAGO COMPLETO → cuota Pagada ──────────────────────────────────────
    sep("8. PAGO — Pago completo (cuota → Pagada)")

    pago2_body = {
        "propiedad_id": P_ID,
        "fecha_pago": str(date.today()),
        "valor_total": "300000",
        "metodo_pago": "Transferencia",
        "detalles": [{"cuota_id": CUOTA1_ID, "monto_aplicado": "300000"}],
    }
    r = client.post(f"{BASE}/api/pagos", json=pago2_body, headers=ADM_HDR)
    check(r.status_code == 201, "POST /api/pagos (pago restante 300k) → 201", f"ERROR: {r.text}")
    PAGO2_ID = r.json()["id"] if r.status_code == 201 else None

    r = client.get(f"{BASE}/api/cuotas/{CUOTA1_ID}", headers=ADM_HDR)
    det = r.json()
    check(det["estado"] == "Pagada", "Cuota cambió a estado=Pagada", f"Estado={det['estado']}")
    check(det["saldo_pendiente"] == "0.00", "saldo_pendiente=0.00", f"saldo_pendiente={det.get('saldo_pendiente')}")

    # Intentar pagar cuota ya Pagada → 400
    r = client.post(f"{BASE}/api/pagos", json={
        "propiedad_id": P_ID, "fecha_pago": str(date.today()),
        "valor_total": "100", "metodo_pago": "Efectivo",
        "detalles": [{"cuota_id": CUOTA1_ID, "monto_aplicado": "100"}],
    }, headers=ADM_HDR)
    check(r.status_code == 400, "POST /api/pagos en cuota Pagada → 400", f"Esperaba 400, recibió {r.status_code}: {r.text}")

    # ── 9. SALDO A FAVOR ──────────────────────────────────────────────────────
    sep("9. SALDO A FAVOR — Pago con excedente")

    # Cuota 2 tiene valor_base=500000, interes=0 → deuda=500000
    # Pagamos 600000 → excedente=100000 → saldo a favor
    pago3_body = {
        "propiedad_id": P_ID,
        "fecha_pago": str(date.today()),
        "valor_total": "600000",
        "metodo_pago": "PSE",
        "detalles": [{"cuota_id": CUOTA2_ID, "monto_aplicado": "500000"}],
    }
    r = client.post(f"{BASE}/api/pagos", json=pago3_body, headers=ADM_HDR)
    check(r.status_code == 201, "POST /api/pagos (600k sobre cuota de 500k) → 201", f"ERROR: {r.text}")

    # Verificar que cuota 2 quedó Pagada
    r = client.get(f"{BASE}/api/cuotas/{CUOTA2_ID}", headers=ADM_HDR)
    check(r.json()["estado"] == "Pagada", "Cuota2 → Pagada", f"Estado={r.json()['estado']}")

    # Verificar saldo a favor
    r = client.get(f"{BASE}/api/saldos-a-favor", headers=ADM_HDR)
    check(r.status_code == 200, f"GET /api/saldos-a-favor → 200", f"ERROR: {r.text}")
    saldos = r.json()
    check(len(saldos) == 1, "1 saldo a favor disponible", f"Esperaba 1, obtuvo {len(saldos)}")
    if saldos:
        saldo = saldos[0]
        SALDO_ID = saldo["id"]
        check(saldo["monto"] == "100000.00", "Saldo a favor = 100000.00", f"monto={saldo['monto']}")
        check(saldo["estado"] == "Disponible", "Saldo estado=Disponible", f"estado={saldo['estado']}")

        # Necesitamos una cuota nueva para aplicar el saldo
        # Crear cuota para 2026-02
        r = client.post(f"{BASE}/api/cuotas/generar", json={"periodo": "2026-02"}, headers=ADM_HDR)
        if r.status_code == 201 and r.json():
            CUOTA3_ID = r.json()[0]["id"]

            # Aplicar saldo a favor a cuota 3 — saldo=100k < deuda=500k → cuota queda Parcial
            r = client.post(f"{BASE}/api/saldos-a-favor/{SALDO_ID}/aplicar",
                            json={"cuota_id": CUOTA3_ID}, headers=ADM_HDR)
            check(r.status_code == 200, "POST /api/saldos-a-favor/aplicar → 200", f"ERROR: {r.text}")
            if r.status_code == 200:
                saldo_resp = r.json()
                check(saldo_resp["estado"] == "Aplicado", "Saldo estado=Aplicado", f"estado={saldo_resp['estado']}")

                r = client.get(f"{BASE}/api/cuotas/{CUOTA3_ID}", headers=ADM_HDR)
                check(r.json()["estado"] == "Parcial",
                      "Cuota3 → Parcial tras aplicar saldo",
                      f"Estado={r.json()['estado']}")

            # Intentar aplicar saldo ya aplicado → 400
            r = client.post(f"{BASE}/api/saldos-a-favor/{SALDO_ID}/aplicar",
                            json={"cuota_id": CUOTA3_ID}, headers=ADM_HDR)
            check(r.status_code == 400, "POST aplicar saldo ya Aplicado → 400", f"Esperaba 400, recibió {r.status_code}")

    # ── 10. ANULAR PAGO ───────────────────────────────────────────────────────
    sep("10. PAGOS — Anular pago (soft delete)")

    if PAGO1_ID:
        r = client.delete(f"{BASE}/api/pagos/{PAGO1_ID}", headers=ADM_HDR)
        check(r.status_code == 204, f"DELETE /api/pagos/{{id}} → 204", f"ERROR: {r.status_code} {r.text}")

        # El pago no debe aparecer en la lista
        r = client.get(f"{BASE}/api/pagos", headers=ADM_HDR)
        ids = [p["id"] for p in r.json()]
        check(PAGO1_ID not in ids, "Pago anulado no aparece en GET /api/pagos", "Pago anulado sigue apareciendo")

        # DELETE de pago inexistente o ya eliminado → 404
        r = client.delete(f"{BASE}/api/pagos/{PAGO1_ID}", headers=ADM_HDR)
        check(r.status_code == 404, "DELETE pago ya eliminado → 404", f"Esperaba 404, recibió {r.status_code}")

    # ── 11. ENDPOINTS INTERNOS ────────────────────────────────────────────────
    sep("11. ENDPOINTS INTERNOS — /internal/*")

    # Sin token → 422 (header requerido faltante)
    r = client.post(f"{BASE}/internal/generar-cuotas?periodo=2026-04")
    check(r.status_code == 422, "POST /internal/generar-cuotas sin header → 422", f"Esperaba 422, recibió {r.status_code}")

    # Token incorrecto → 401
    r = client.post(f"{BASE}/internal/generar-cuotas?periodo=2026-04",
                    headers={"X-Internal-Token": "token_incorrecto"})
    check(r.status_code == 401, "POST /internal/generar-cuotas con token incorrecto → 401", f"Esperaba 401, recibió {r.status_code}")

    # Token correcto → 200
    r = client.post(f"{BASE}/internal/generar-cuotas?periodo=2026-04", headers=INT_HDR)
    check(r.status_code == 200, "POST /internal/generar-cuotas (token válido) → 200", f"ERROR: {r.text}")
    if r.status_code == 200:
        body = r.json()
        check("resultados" in body and "periodo" in body,
              f"Respuesta contiene 'resultados' y 'periodo'",
              f"Respuesta inesperada: {body}")
        # Verificar que el conjunto de test aparece en resultados
        resultado_test = next((x for x in body["resultados"] if x["conjunto_id"] == C_ID), None)
        check(resultado_test is not None and resultado_test.get("cuotas_generadas", 0) == 1,
              f"Conjunto de test generó 1 cuota en 2026-04",
              f"Resultado del conjunto de test: {resultado_test}")

    # Sin token → 422
    r = client.post(f"{BASE}/internal/calcular-intereses")
    check(r.status_code == 422, "POST /internal/calcular-intereses sin header → 422", f"Esperaba 422, recibió {r.status_code}")

    # Token correcto → 200
    r = client.post(f"{BASE}/internal/calcular-intereses", headers=INT_HDR)
    check(r.status_code == 200, "POST /internal/calcular-intereses (token válido) → 200", f"ERROR: {r.text}")
    if r.status_code == 200:
        body = r.json()
        check("resultados" in body and "mes_ejecucion" in body,
              "Respuesta contiene 'resultados' y 'mes_ejecucion'",
              f"Respuesta inesperada: {body}")
        resultado_test = next((x for x in body["resultados"] if x["conjunto_id"] == C_ID), None)
        info(f"Intereses para conjunto de test: {resultado_test}")


# ══════════════════════════════════════════════════════════════════════════════
# ENTRY POINT
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    conjunto_id = None
    auth_user_id = None

    try:
        # Setup
        conjunto_id, propiedad_id, auth_user_id = setup_datos()

        # Login admin user para obtener el JWT con conjunto_id
        sep("LOGIN — Usuario admin de prueba")
        r = client.post(f"{BASE}/auth/login",
                        json={"email": TEST_ADMIN_EMAIL, "password": TEST_ADMIN_PASS})
        print(f"  POST /auth/login (admin test) -> {r.status_code}")
        if r.status_code != 200:
            print(f"  [ABORT] No se pudo hacer login: {r.text}")
            sys.exit(1)

        admin_token = r.json()["data"]["access_token"]
        ok("Login exitoso, token obtenido")

        # Ejecutar todos los tests
        run_tests(conjunto_id, propiedad_id, admin_token)

    except Exception as e:
        import traceback
        print(f"\n  [ERROR FATAL] {e}")
        traceback.print_exc()
    finally:
        client.close()
        cleanup_datos(_created_conjunto_id, _created_auth_user_id)

        print(f"\n{'='*60}")
        if _fail_count == 0:
            print(f"  RESULTADO: TODOS LOS TESTS PASARON [OK]")
        else:
            print(f"  RESULTADO: {_fail_count} test(s) FALLARON [FAIL]")
        print(f"{'='*60}\n")
        sys.exit(0 if _fail_count == 0 else 1)
