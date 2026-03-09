"""
test_fase4.py - Prueba integral de Fase 4: Notificaciones WhatsApp.

Estrategia:
  - Verifica que los endpoints de notificacion existen y responden correctamente.
  - Verifica que generar-cuotas incluye el campo notificaciones_enviadas.
  - Verifica que pago registrado sigue funcionando (no se rompio con el hook WS).
  - WhatsApp real NO se prueba (credenciales de produccion no disponibles en test).
  - Prueba directa de whatsapp_service._fmt_ws y degradacion sin credenciales.

Prerrequisitos:
  - Servidor en http://localhost:8000
  - .env con credenciales validas en V1.0/

Ejecutar desde V1.0/:  python test_fase4.py
"""

import sys
import uuid
from datetime import date, datetime
from decimal import Decimal

import httpx
from dotenv import load_dotenv

load_dotenv(".env")
sys.path.insert(0, ".")

from ph_saas.config import settings, BOGOTA_TZ
from ph_saas.database import SessionLocal
from ph_saas.models.conjunto import Conjunto
from ph_saas.models.configuracion_conjunto import ConfiguracionConjunto
from ph_saas.models.cuota import Cuota
from ph_saas.models.propiedad import Propiedad
from ph_saas.models.suscripcion import SuscripcionSaaS
from ph_saas.models.usuario import Usuario
from ph_saas.models.usuario_conjunto import UsuarioConjunto

from supabase import create_client

# ── Constantes ─────────────────────────────────────────────────────────────────

BASE             = "http://localhost:8000"
_TEST_UID        = uuid.uuid4().hex[:6]
TEST_ADMIN_EMAIL = f"test_f4_{_TEST_UID}@test.com"
TEST_ADMIN_PASS  = "TestPass123$"
TEST_PERIODO     = "2025-11"   # Periodo pasado, cuotas venceran inmediatamente
INTERNAL_TOKEN   = settings.INTERNAL_TOKEN
TIMEOUT          = httpx.Timeout(25.0, connect=10.0)

_supabase = create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_ROLE_KEY)

_created_conjunto_id  : uuid.UUID | None = None
_created_auth_user_id : str | None       = None

# ── Helpers de output ─────────────────────────────────────────────────────────

def ok(msg):   print(f"  [OK]   {msg}")
def fail(msg): print(f"  [FAIL] {msg}")
def info(msg): print(f"  [INFO] {msg}")
def skip(msg): print(f"  [SKIP] {msg}")
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


# ── Setup de datos ─────────────────────────────────────────────────────────────

def setup_datos():
    global _created_conjunto_id, _created_auth_user_id

    sep("SETUP - Creando datos de prueba para Fase 4")
    db = SessionLocal()
    try:
        conjunto = Conjunto(
            nombre=f"Conjunto F4 {_TEST_UID}",
            nit=f"90{_TEST_UID}",
            direccion="Calle F4 Test",
            ciudad="Bogota",
        )
        db.add(conjunto)
        db.flush()
        _created_conjunto_id = conjunto.id

        suscripcion = SuscripcionSaaS(
            conjunto_id=conjunto.id,
            estado="Activo",
            fecha_vencimiento=date(2099, 12, 31),
            valor_mensual=Decimal("50000"),
        )
        db.add(suscripcion)

        config = ConfiguracionConjunto(
            conjunto_id=conjunto.id,
            valor_cuota_estandar=Decimal("250000"),
            tasa_interes_mora=Decimal("2.00"),
            permitir_interes=True,
            dia_notificacion_mora=5,
        )
        db.add(config)

        propiedad = Propiedad(
            conjunto_id=conjunto.id,
            numero_apartamento="201",
            estado="Activo",
        )
        db.add(propiedad)
        db.flush()

        # Cuota vencida para test de mora
        from dateutil.relativedelta import relativedelta
        from datetime import timedelta
        year, month = 2025, 11
        fecha_venc = date(year, month, 1) + relativedelta(months=1) - timedelta(days=1)
        cuota = Cuota(
            conjunto_id=conjunto.id,
            propiedad_id=propiedad.id,
            periodo=TEST_PERIODO,
            valor_base=Decimal("250000"),
            interes_generado=Decimal("0"),
            estado="Vencida",
            fecha_vencimiento=fecha_venc,
        )
        db.add(cuota)

        db.commit()
        ok(f"Conjunto creado: {conjunto.id}")
        ok(f"Propiedad 201 y cuota vencida {TEST_PERIODO} creadas")

        # Usuario admin en Supabase Auth
        info(f"Creando usuario admin en Supabase Auth: {TEST_ADMIN_EMAIL}")
        resp = _supabase.auth.admin.create_user({
            "email": TEST_ADMIN_EMAIL,
            "password": TEST_ADMIN_PASS,
            "email_confirm": True,
            "app_metadata": {"role": "user", "conjunto_id": str(conjunto.id)},
        })
        auth_id = resp.user.id
        _created_auth_user_id = auth_id
        ok(f"Usuario Supabase creado: {auth_id[:8]}...")

        usuario = Usuario(
            id=uuid.UUID(auth_id),
            nombre="Admin F4 Test",
            correo=TEST_ADMIN_EMAIL,
            telefono_ws=None,  # Sin telefono para este test
        )
        db.add(usuario)

        uc = UsuarioConjunto(
            usuario_id=uuid.UUID(auth_id),
            conjunto_id=conjunto.id,
            rol="Administrador",
        )
        db.add(uc)
        db.commit()
        ok("UsuarioConjunto rol=Administrador asignado")

        return conjunto.id, propiedad.id

    finally:
        db.close()


def cleanup_datos(conjunto_id, auth_user_id):
    sep("CLEANUP - Eliminando datos de prueba")
    if not conjunto_id:
        return
    db = SessionLocal()
    try:
        from ph_saas.models.cuota import Cuota as CuotaM
        from ph_saas.models.pago import Pago
        from ph_saas.models.pago_detalle import PagoDetalle
        from ph_saas.models.movimiento_contable import MovimientoContable
        from ph_saas.models.proceso_log import ProcesoLog

        from ph_saas.models.cuota_interes_log import CuotaInteresLog
        cuotas_ids = [c.id for c in db.query(CuotaM).filter(CuotaM.conjunto_id == conjunto_id).all()]
        if cuotas_ids:
            db.query(CuotaInteresLog).filter(CuotaInteresLog.cuota_id.in_(cuotas_ids)).delete(synchronize_session=False)
        pagos_ids = [p.id for p in db.query(Pago).filter(Pago.conjunto_id == conjunto_id).all()]
        db.query(PagoDetalle).filter(PagoDetalle.pago_id.in_(pagos_ids)).delete(synchronize_session=False)
        db.query(Pago).filter(Pago.conjunto_id == conjunto_id).delete()
        db.query(MovimientoContable).filter(MovimientoContable.conjunto_id == conjunto_id).delete()
        db.query(ProcesoLog).filter(ProcesoLog.conjunto_id == conjunto_id).delete()
        db.query(CuotaM).filter(CuotaM.conjunto_id == conjunto_id).delete()
        db.query(UsuarioConjunto).filter(UsuarioConjunto.conjunto_id == conjunto_id).delete()
        db.query(Usuario).filter(Usuario.id == uuid.UUID(auth_user_id)).delete()
        db.query(Propiedad).filter(Propiedad.conjunto_id == conjunto_id).delete()
        db.query(ConfiguracionConjunto).filter(ConfiguracionConjunto.conjunto_id == conjunto_id).delete()
        db.query(SuscripcionSaaS).filter(SuscripcionSaaS.conjunto_id == conjunto_id).delete()
        db.query(Conjunto).filter(Conjunto.id == conjunto_id).delete()
        db.commit()
        ok(f"Registros BD eliminados para conjunto {conjunto_id}")
    except Exception as e:
        print(f"  [WARN] Error en cleanup BD: {e}")
    finally:
        db.close()

    if auth_user_id:
        try:
            _supabase.auth.admin.delete_user(auth_user_id)
            ok(f"Usuario Supabase Auth eliminado: {auth_user_id[:8]}...")
        except Exception as e:
            print(f"  [WARN] Error eliminando usuario Supabase: {e}")


# ── Tests ──────────────────────────────────────────────────────────────────────

def run_tests(conjunto_id, propiedad_id, admin_token):
    ADM_HDR = {"Authorization": f"Bearer {admin_token}"}
    INT_HDR = {"X-Internal-Token": INTERNAL_TOKEN}
    CONJUNTO_ID = str(conjunto_id)
    PROPIEDAD_ID = str(propiedad_id)

    # ====== 1. WHATSAPP SERVICE - degradacion sin credenciales ================
    sep("1. WhatsApp Service - degradacion sin credenciales")
    from ph_saas.services.whatsapp_service import (
        _fmt_ws,
        _get_twilio_client,
        notificar_confirmacion_pago,
        notificar_paz_y_salvo,
    )

    check(_fmt_ws(None) is None,        "_fmt_ws(None) retorna None", "_fmt_ws(None) no retorna None")
    check(_fmt_ws("") is None,          "_fmt_ws('') retorna None",   "_fmt_ws('') no retorna None")
    check(_fmt_ws("3001234567") == "whatsapp:+3001234567",
          "_fmt_ws('3001234567') = 'whatsapp:+3001234567'",
          f"_fmt_ws('3001234567') = {_fmt_ws('3001234567')}")
    check(_fmt_ws("+573001234567") == "whatsapp:+573001234567",
          "_fmt_ws('+573001234567') = 'whatsapp:+573001234567'",
          f"_fmt_ws('+573001234567') = {_fmt_ws('+573001234567')}")
    check(_fmt_ws("whatsapp:+573001234567") == "whatsapp:+573001234567",
          "_fmt_ws ya con prefijo no duplica 'whatsapp:'",
          f"_fmt_ws duplica prefijo: {_fmt_ws('whatsapp:+573001234567')}")

    twilio_client = _get_twilio_client()
    if twilio_client is None:
        info("TWILIO_ACCOUNT_SID no configurado - modo degradado activo (esperado en dev)")
        # Verificar que las funciones NO fallan cuando no hay credenciales
        result = notificar_confirmacion_pago(None, "Test", "201", Decimal("100000"), date.today())
        check(result is False, "notificar_confirmacion_pago(None) retorna False sin credenciales",
              "notificar_confirmacion_pago(None) fallo inesperadamente")
        result2 = notificar_paz_y_salvo("+57300000", "Test", "201")
        check(result2 is False, "notificar_paz_y_salvo retorna False sin credenciales",
              "notificar_paz_y_salvo fallo inesperadamente")
    else:
        info("TWILIO_ACCOUNT_SID configurado - cliente activo")
        check(twilio_client is not None, "Cliente Twilio creado", "No se creo cliente Twilio")

    # ====== 2. ENDPOINT /internal/notificar-mora ==============================
    sep("2. POST /internal/notificar-mora")
    r = client.post(f"{BASE}/internal/notificar-mora", headers=INT_HDR)
    print(f"  POST /internal/notificar-mora -> {r.status_code}")
    check(r.status_code == 200,
          "POST /internal/notificar-mora retorna 200",
          f"ERROR: {r.text}")
    if r.status_code == 200:
        d = r.json()
        check("resultados" in d,
              "Respuesta tiene campo 'resultados'",
              f"Respuesta inesperada: {d}")
        if "resultados" in d:
            info(f"Resultados: {len(d['resultados'])} conjuntos procesados")
            # Verificar que nuestro conjunto aparece
            encontrado = any(res.get("conjunto_id") == CONJUNTO_ID for res in d["resultados"])
            check(encontrado,
                  f"Conjunto {CONJUNTO_ID[:8]}... aparece en resultados",
                  f"Conjunto no encontrado en resultados. IDs: {[r.get('conjunto_id','')[:8] for r in d['resultados']]}")
            if encontrado:
                res_conjunto = next(r for r in d["resultados"] if r.get("conjunto_id") == CONJUNTO_ID)
                check("notificaciones_enviadas" in res_conjunto,
                      f"Campo notificaciones_enviadas presente (={res_conjunto.get('notificaciones_enviadas')})",
                      "Falta campo notificaciones_enviadas en resultado")

    # ====== 3. /internal/notificar-mora sin token retorna 422 =================
    sep("3. POST /internal/notificar-mora sin token -> 422")
    r = client.post(f"{BASE}/internal/notificar-mora")
    check(r.status_code == 422,
          f"POST /internal/notificar-mora sin token -> 422",
          f"Esperaba 422, recibi {r.status_code}")

    # ====== 4. /internal/notificar-mora con token invalido -> 401 =============
    sep("4. POST /internal/notificar-mora con token invalido -> 401")
    r = client.post(f"{BASE}/internal/notificar-mora", headers={"X-Internal-Token": "token_invalido"})
    check(r.status_code == 401,
          "POST /internal/notificar-mora token invalido -> 401",
          f"Esperaba 401, recibi {r.status_code}")

    # ====== 5. /internal/generar-cuotas incluye notificaciones_enviadas =======
    sep("5. POST /internal/generar-cuotas incluye notificaciones_enviadas")
    periodo_nuevo = "2099-01"  # Periodo futuro para no chocar con datos existentes
    r = client.post(f"{BASE}/internal/generar-cuotas?periodo={periodo_nuevo}", headers=INT_HDR)
    print(f"  POST /internal/generar-cuotas?periodo={periodo_nuevo} -> {r.status_code}")
    check(r.status_code == 200, "generar-cuotas retorna 200", f"ERROR: {r.text}")
    if r.status_code == 200:
        d = r.json()
        check("resultados" in d, "Respuesta tiene 'resultados'", f"Falta 'resultados': {d}")
        if "resultados" in d and d["resultados"]:
            primer_resultado = d["resultados"][0]
            check(
                "notificaciones_enviadas" in primer_resultado,
                f"Resultado incluye 'notificaciones_enviadas' (={primer_resultado.get('notificaciones_enviadas')})",
                f"Falta 'notificaciones_enviadas' en resultado. Campos: {list(primer_resultado.keys())}"
            )

    # ====== 6. Pago sigue funcionando (regresion) =============================
    sep("6. Regresion: POST /api/pagos sigue funcionando con hook WS")
    # Obtener cuota vencida para pagar
    r = client.get(f"{BASE}/api/cuotas?propiedad_id={PROPIEDAD_ID}", headers=ADM_HDR)
    check(r.status_code == 200, "GET /api/cuotas -> 200", f"ERROR: {r.text}")
    cuota_id = None
    if r.status_code == 200:
        cuotas = r.json()
        if cuotas:
            cuota_id = cuotas[0]["id"]
            info(f"Cuota disponible: {cuota_id[:8]}... estado={cuotas[0]['estado']}")

    if cuota_id:
        pago_body = {
            "propiedad_id": PROPIEDAD_ID,
            "fecha_pago": str(date.today()),
            "valor_total": 250000,
            "metodo_pago": "Efectivo",
            "referencia": f"Test F4 {_TEST_UID}",
            "detalles": [{"cuota_id": cuota_id, "monto_aplicado": 250000}],
        }
        r = client.post(f"{BASE}/api/pagos", json=pago_body, headers=ADM_HDR)
        print(f"  POST /api/pagos -> {r.status_code}")
        check(r.status_code == 201,
              "POST /api/pagos -> 201 (pago registrado + notificacion WS no bloquea)",
              f"ERROR: {r.text}")
        if r.status_code == 201:
            d = r.json()
            # El router retorna PagoConDetalle directamente (no envuelto en 'data')
            check("id" in d, f"Pago creado id={d.get('id','?')[:8]}...",
                  f"Respuesta inesperada: {d}")
    else:
        info("Sin cuota disponible para pagar, omitiendo test de regresion de pago")

    # ====== 7. Endpoints internos completos OK ================================
    sep("7. Todos los endpoints /internal/ existentes")
    endpoints_internos = [
        ("POST", "/internal/generar-cuotas?periodo=2099-02"),
        ("POST", "/internal/calcular-intereses"),
        ("POST", "/internal/notificar-mora"),
    ]
    for method, path in endpoints_internos:
        r = client.request(method, f"{BASE}{path}", headers=INT_HDR)
        check(r.status_code == 200,
              f"{method} {path} -> 200",
              f"{method} {path} -> {r.status_code}: {r.text[:100]}")


# ── Entry point ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    conjunto_id = propiedad_id = None

    try:
        conjunto_id, propiedad_id = setup_datos()

        sep("LOGIN - Usuario admin de prueba")
        r = client.post(f"{BASE}/auth/login", json={"email": TEST_ADMIN_EMAIL, "password": TEST_ADMIN_PASS})
        if r.status_code != 200:
            print(f"  [ERROR] Login fallido: {r.text}")
            sys.exit(1)
        admin_token = r.json()["data"]["access_token"]
        ok(f"Login OK - token obtenido")

        run_tests(conjunto_id, propiedad_id, admin_token)

    finally:
        cleanup_datos(_created_conjunto_id, _created_auth_user_id)

    sep("RESULTADO FINAL")
    if _fail_count == 0:
        print("  RESULTADO: TODOS LOS TESTS PASARON [OK]")
    else:
        print(f"  RESULTADO: {_fail_count} TEST(S) FALLARON [FAIL]")
        sys.exit(1)
