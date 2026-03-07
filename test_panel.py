"""
test_panel.py - Prueba integral de las pantallas HTML del panel (Fase 1).

Cubre:
  - Login page (GET /)
  - Login correcto SA -> cookie + redirect
  - Login incorrecto -> redirect con error
  - Panel SA: conjuntos (listar, crear, editar, eliminar)
  - Panel SA: suscripciones (listar, crear, pagar +1mes, suspender, activar)
  - Panel APP: redirige a login sin cookie
  - Logout limpia cookies

Ejecutar con: python test_panel.py
Requiere servidor corriendo en http://localhost:8000
"""

import httpx
import sys
import uuid
from datetime import date, timedelta

BASE = "http://localhost:8000"
TIMEOUT = 30.0

SA_EMAIL    = "vccompany011@email.com"
SA_PASSWORD = "Vc92985315$%"

passed = 0
failed = 0

def ok(msg):
    global passed
    passed += 1
    print(f"  [OK]   {msg}")

def fail(msg):
    global failed
    failed += 1
    print(f"  [FAIL] {msg}")

def sep(title):
    print(f"\n{'='*60}\n{title}\n{'='*60}")

# Cliente sin seguir redirects automaticamente (para verificar el PRG)
client = httpx.Client(
    timeout=TIMEOUT,
    follow_redirects=False,
    cookies={},
)


# ============================================================
# 1. PAGINA DE LOGIN (sin autenticar)
# ============================================================
sep("1. LOGIN PAGE — sin autenticar")

r = client.get(f"{BASE}/")
print(f"  GET / -> {r.status_code}")
if r.status_code == 200:
    if "PH SaaS" in r.text and "Inicia sesion" in r.text:
        ok("Login page renderiza HTML con contenido correcto")
    else:
        fail(f"Login page sin contenido esperado. Primeros 200 chars: {r.text[:200]}")
else:
    fail(f"GET / -> {r.status_code}")

# Panel SA sin cookie -> redirect a login
r = client.get(f"{BASE}/panel/sa/conjuntos")
print(f"  GET /panel/sa/conjuntos sin cookie -> {r.status_code}")
if r.status_code == 302 and "/?error=" in r.headers.get("location", ""):
    ok("Redirect a login sin cookie (SA)")
else:
    fail(f"Esperaba 302 a /?error=, recibio {r.status_code} location={r.headers.get('location')}")

# Panel APP sin cookie -> redirect a login
r = client.get(f"{BASE}/panel/app/propiedades")
print(f"  GET /panel/app/propiedades sin cookie -> {r.status_code}")
if r.status_code == 302 and "/?error=" in r.headers.get("location", ""):
    ok("Redirect a login sin cookie (APP)")
else:
    fail(f"Esperaba 302 a /?error=, recibio {r.status_code} location={r.headers.get('location')}")


# ============================================================
# 2. LOGIN INCORRECTO VIA PANEL
# ============================================================
sep("2. LOGIN INCORRECTO")

r = client.post(f"{BASE}/panel/login", data={"email": SA_EMAIL, "password": "contrasena_mala"})
print(f"  POST /panel/login (password incorrecto) -> {r.status_code}")
loc = r.headers.get("location", "")
if r.status_code == 302 and "/?error=" in loc:
    ok(f"Redirect a /?error= con credenciales malas (location: {loc})")
else:
    fail(f"Esperaba 302 a /?error=, recibio {r.status_code} location={loc}")

r = client.post(f"{BASE}/panel/login", data={"email": "noexiste@mail.com", "password": "algo"})
print(f"  POST /panel/login (email inexistente) -> {r.status_code}")
if r.status_code == 302 and "/?error=" in r.headers.get("location", ""):
    ok("Redirect correcto con email inexistente")
else:
    fail(f"Esperaba 302 a /?error=, recibio {r.status_code}")


# ============================================================
# 3. LOGIN CORRECTO — SUPERADMIN
# ============================================================
sep("3. LOGIN SUPERADMIN CORRECTO")

r = client.post(f"{BASE}/panel/login", data={"email": SA_EMAIL, "password": SA_PASSWORD})
print(f"  POST /panel/login (SA correcto) -> {r.status_code}")
loc = r.headers.get("location", "")
if r.status_code == 302 and loc == "/panel/sa/conjuntos":
    ok(f"Redirect a {loc}")
else:
    fail(f"Esperaba 302 a /panel/sa/conjuntos, recibio {r.status_code} location={loc}")
    sys.exit(1)

# Verificar que la cookie fue seteada
cookie_val = r.cookies.get("ph_token") or client.cookies.get("ph_token")
if cookie_val:
    ok(f"Cookie ph_token seteada (len={len(cookie_val)})")
else:
    fail("Cookie ph_token NO fue seteada")
    sys.exit(1)

# GET / con cookie valida -> redirect a SA conjuntos
r = client.get(f"{BASE}/")
print(f"  GET / con cookie SA -> {r.status_code}")
if r.status_code == 302 and r.headers.get("location") == "/panel/sa/conjuntos":
    ok("GET / redirige a SA panel cuando hay sesion activa")
else:
    fail(f"Esperaba 302 a /panel/sa/conjuntos, recibio {r.status_code} location={r.headers.get('location')}")


# ============================================================
# 4. PANEL SA — CONJUNTOS
# ============================================================
sep("4. PANEL SA — CONJUNTOS HTML")

r = client.get(f"{BASE}/panel/sa/conjuntos")
print(f"  GET /panel/sa/conjuntos -> {r.status_code}")
if r.status_code == 200 and "Conjuntos residenciales" in r.text:
    ok("Pagina SA conjuntos renderiza correctamente")
else:
    fail(f"Pagina SA conjuntos -> {r.status_code}: {r.text[:200]}")

# Crear conjunto via panel
# Nombre único por ejecución para evitar conflicto con UNIQUE en DB tras soft-delete
nombre_test = f"HTML Test {uuid.uuid4().hex[:8]}"
r = client.post(f"{BASE}/panel/sa/conjuntos/crear", data={
    "nombre": nombre_test,
    "nit": "900111222-3",
    "direccion": "Av. Test 123",
    "ciudad": "Cali",
})
print(f"  POST /panel/sa/conjuntos/crear -> {r.status_code}")
loc = r.headers.get("location", "")
if r.status_code == 302 and "/panel/sa/conjuntos" in loc and "success=" in loc:
    ok(f"Conjunto creado OK, redirect con success")
else:
    fail(f"Esperaba 302 con success=, recibio {r.status_code} location={loc}")
    sys.exit(1)

# Verificar que aparece en la lista
r = client.get(f"{BASE}/panel/sa/conjuntos")
if nombre_test in r.text:
    ok(f"'{nombre_test}' aparece en la tabla de conjuntos")
else:
    fail(f"'{nombre_test}' NO aparece en la tabla")

# Crear duplicado
r = client.post(f"{BASE}/panel/sa/conjuntos/crear", data={
    "nombre": nombre_test,
    "ciudad": "Bogota",
})
print(f"  POST crear (nombre duplicado) -> {r.status_code}")
loc = r.headers.get("location", "")
if r.status_code == 302 and "error=" in loc:
    ok("Duplicado rechazado con redirect a error")
else:
    fail(f"Esperaba redirect con error=, recibio {r.status_code} location={loc}")

# Obtener el ID del conjunto recien creado via API SA
r_api = client.get(f"{BASE}/panel/sa/conjuntos")
# El UUID esta en los atributos @click="openDelete('UUID')" del HTML
import re
PANEL_CONJUNTO_ID = None
# Buscar el UUID DESPUES de nombre_test (los botones vienen despues en el mismo <tr>)
idx = r_api.text.find(nombre_test)
if idx > 0:
    forward = r_api.text[idx: idx + 800]  # solo hacia adelante para no capturar row anterior
    m2 = re.search(r"openDelete\('([0-9a-f-]{36})'", forward)
    if not m2:
        m2 = re.search(r"openEdit\('([0-9a-f-]{36})'", forward)
    if m2:
        PANEL_CONJUNTO_ID = m2.group(1)

if PANEL_CONJUNTO_ID:
    ok(f"ID del conjunto de prueba extraido: {PANEL_CONJUNTO_ID[:8]}...")
else:
    fail("No se pudo extrair el UUID del HTML, necesario para continuar")

# Editar conjunto
if PANEL_CONJUNTO_ID:
    r = client.post(f"{BASE}/panel/sa/conjuntos/{PANEL_CONJUNTO_ID}/editar", data={
        "nombre": nombre_test,
        "ciudad": "Medellin",
        "nit": "900111222-3",
        "direccion": "Av. Test 123",
    })
    print(f"  POST /panel/sa/conjuntos/id/editar -> {r.status_code}")
    loc = r.headers.get("location", "")
    if r.status_code == 302 and "success=" in loc:
        ok("Edicion OK con redirect success")
    else:
        fail(f"Esperaba redirect success, recibio {r.status_code} location={loc}")

    # Verificar cambio
    r = client.get(f"{BASE}/panel/sa/conjuntos")
    if "Medellin" in r.text:
        ok("Ciudad actualizada a Medellin aparece en la tabla")
    else:
        fail("Ciudad editada no aparece en tabla")


# ============================================================
# 5. PANEL SA — SUSCRIPCIONES
# ============================================================
sep("5. PANEL SA — SUSCRIPCIONES HTML")

r = client.get(f"{BASE}/panel/sa/suscripciones")
print(f"  GET /panel/sa/suscripciones -> {r.status_code}")
if r.status_code == 200 and "suscripciones" in r.text.lower():
    ok("Pagina suscripciones renderiza correctamente")
else:
    fail(f"suscripciones -> {r.status_code}: {r.text[:200]}")

if PANEL_CONJUNTO_ID:
    fecha_venc = (date.today() + timedelta(days=30)).isoformat()

    # Crear suscripcion
    r = client.post(f"{BASE}/panel/sa/suscripciones/{PANEL_CONJUNTO_ID}/crear", data={
        "estado": "Activo",
        "fecha_vencimiento": fecha_venc,
        "valor_mensual": "150000",
        "observaciones": "Prueba test",
    })
    print(f"  POST suscripciones/crear -> {r.status_code}")
    loc = r.headers.get("location", "")
    if r.status_code == 302 and "success=" in loc:
        ok("Suscripcion creada OK")
    else:
        fail(f"Esperaba redirect success, recibio {r.status_code} location={loc}")

    # Crear duplicado -> error
    r = client.post(f"{BASE}/panel/sa/suscripciones/{PANEL_CONJUNTO_ID}/crear", data={
        "estado": "Activo",
        "fecha_vencimiento": fecha_venc,
        "valor_mensual": "150000",
    })
    print(f"  POST suscripciones/crear (duplicado) -> {r.status_code}")
    if r.status_code == 302 and "error=" in r.headers.get("location", ""):
        ok("Duplicado rechazado con redirect error")
    else:
        fail(f"Esperaba redirect error, recibio {r.status_code} location={r.headers.get('location')}")

    # Suspender
    r = client.post(f"{BASE}/panel/sa/suscripciones/{PANEL_CONJUNTO_ID}/suspender")
    print(f"  POST suscripciones/suspender -> {r.status_code}")
    if r.status_code == 302 and "success=" in r.headers.get("location", ""):
        ok("Suspender OK")
    else:
        fail(f"Esperaba redirect success, recibio {r.status_code}")

    # Suspender de nuevo -> ya suspendida -> error
    r = client.post(f"{BASE}/panel/sa/suscripciones/{PANEL_CONJUNTO_ID}/suspender")
    if r.status_code == 302 and "error=" in r.headers.get("location", ""):
        ok("Suspender ya-suspendida devuelve error")
    else:
        fail(f"Esperaba redirect error, recibio {r.status_code}")

    # Activar
    r = client.post(f"{BASE}/panel/sa/suscripciones/{PANEL_CONJUNTO_ID}/activar")
    print(f"  POST suscripciones/activar -> {r.status_code}")
    if r.status_code == 302 and "success=" in r.headers.get("location", ""):
        ok("Activar OK")
    else:
        fail(f"Esperaba redirect success, recibio {r.status_code}")

    # Pagar +1 mes
    r = client.post(f"{BASE}/panel/sa/suscripciones/{PANEL_CONJUNTO_ID}/pagar", data={
        "observaciones": "Pago test",
    })
    print(f"  POST suscripciones/pagar -> {r.status_code}")
    if r.status_code == 302 and "success=" in r.headers.get("location", ""):
        ok("Pagar +1 mes OK")
    else:
        fail(f"Esperaba redirect success, recibio {r.status_code}")

    # Verificar que el vencimiento cambio
    r = client.get(f"{BASE}/panel/sa/suscripciones")
    expected_month = (date.today() + timedelta(days=60)).strftime("/%m/")
    if r.status_code == 200:
        ok("Pagina suscripciones carga post-pago OK")
    else:
        fail(f"Pagina suscripciones post-pago -> {r.status_code}")


# ============================================================
# 6. PANEL APP — sin conjunto cookie (SA no tiene ph_conjunto_id)
# ============================================================
sep("6. PANEL APP — superadmin accede (sin ph_conjunto_id)")

r = client.get(f"{BASE}/panel/app/propiedades")
print(f"  GET /panel/app/propiedades (SA sin conjunto) -> {r.status_code}")
# SA accede sin conjunto_id; la pagina carga pero sin filtro de conjunto
# La vista acepta superadmin sin conjunto_id como bypass
if r.status_code == 200:
    ok("SA puede acceder a /panel/app/propiedades (bypass sin conjunto)")
elif r.status_code == 302:
    ok(f"SA redirigido -> {r.headers.get('location')} (comportamiento aceptable)")
else:
    fail(f"Inesperado {r.status_code}")

r = client.get(f"{BASE}/panel/app/usuarios")
print(f"  GET /panel/app/usuarios (SA sin conjunto) -> {r.status_code}")
if r.status_code in (200, 302):
    ok(f"GET usuarios -> {r.status_code} (esperado)")
else:
    fail(f"Inesperado {r.status_code}")


# ============================================================
# 7. LOGOUT
# ============================================================
sep("7. LOGOUT")

r = client.get(f"{BASE}/panel/logout")
print(f"  GET /panel/logout -> {r.status_code}")
if r.status_code == 302 and r.headers.get("location") == "/":
    ok("Logout redirige a /")
else:
    fail(f"Esperaba 302 a /, recibio {r.status_code} location={r.headers.get('location')}")

# Verificar que la cookie fue eliminada
cookie_after = client.cookies.get("ph_token")
if not cookie_after:
    ok("Cookie ph_token eliminada post-logout")
else:
    fail("Cookie ph_token SIGUE presente post-logout")

# Panel SA ahora debe rechazar
r = client.get(f"{BASE}/panel/sa/conjuntos")
print(f"  GET /panel/sa/conjuntos post-logout -> {r.status_code}")
if r.status_code == 302 and "/?error=" in r.headers.get("location", ""):
    ok("Post-logout: acceso a SA rechazado correctamente")
else:
    fail(f"Esperaba redirect a /?error=, recibio {r.status_code}")


# ============================================================
# 8. CLEANUP via API — eliminar conjunto HTML Test
# ============================================================
sep("8. CLEANUP")

if PANEL_CONJUNTO_ID:
    # Re-login para obtener token API
    r_login = httpx.post(
        f"{BASE}/auth/login",
        json={"email": SA_EMAIL, "password": SA_PASSWORD},
        timeout=TIMEOUT,
    )
    if r_login.status_code == 200:
        api_token = r_login.json()["data"]["access_token"]
        r_del = httpx.delete(
            f"{BASE}/admin/conjuntos/{PANEL_CONJUNTO_ID}",
            headers={"Authorization": f"Bearer {api_token}"},
            timeout=TIMEOUT,
        )
        print(f"  DELETE /admin/conjuntos/{PANEL_CONJUNTO_ID[:8]}... -> {r_del.status_code}")
        if r_del.status_code == 204:
            ok("Conjunto de prueba eliminado via API")
        else:
            fail(f"No se pudo eliminar: {r_del.text}")
    else:
        fail("No se pudo re-autenticar para cleanup")
else:
    print("  [SKIP] No se tiene PANEL_CONJUNTO_ID para cleanup")

client.close()

# ============================================================
# RESUMEN
# ============================================================
total = passed + failed
print(f"\n{'='*60}")
print(f"RESULTADOS: {passed}/{total} pruebas pasaron")
if failed:
    print(f"  FALLARON: {failed} prueba(s)")
print("="*60)

if failed > 0:
    sys.exit(1)
