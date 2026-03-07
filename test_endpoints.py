"""
test_endpoints.py - Prueba integral de endpoints de Fase 1.
Ejecutar con: python test_endpoints.py
"""

import httpx
import sys

BASE = "http://localhost:8000"
PASSWORD = "Vc92985315$%"
SUPERADMIN_EMAIL = "vccompany011@email.com"
TIMEOUT = 30.0

def ok(msg): print(f"  [OK]   {msg}")
def fail(msg): print(f"  [FAIL] {msg}")
def sep(title): print(f"\n{'='*55}\n{title}\n{'='*55}")

client = httpx.Client(timeout=TIMEOUT)


# 1. HEALTH
sep("1. HEALTH")
r = client.get(f"{BASE}/health")
if r.status_code == 200 and r.json().get("status") == "ok":
    ok(f"GET /health -> {r.json()}")
else:
    fail(f"GET /health -> {r.status_code}: {r.text}")
    sys.exit(1)


# 2. AUTH
sep("2. AUTH - LOGIN SUPERADMIN")
r = client.post(f"{BASE}/auth/login", json={"email": SUPERADMIN_EMAIL, "password": PASSWORD})
print(f"  POST /auth/login -> {r.status_code}")
if r.status_code != 200:
    fail(f"Login fallido: {r.text}")
    sys.exit(1)

data = r.json()["data"]
TOKEN = data["access_token"]
is_sa = data["user"]["is_superadmin"]
ok(f"Login OK - is_superadmin={is_sa} - token obtenido")

HDR = {"Authorization": f"Bearer {TOKEN}"}

r = client.get(f"{BASE}/auth/me", headers=HDR)
print(f"  GET /auth/me -> {r.status_code}")
if r.status_code == 200:
    ok(f"/auth/me OK: {r.json()['data']['email']}")
else:
    fail(f"/auth/me ERROR: {r.text}")

r = client.post(f"{BASE}/auth/login", json={"email": SUPERADMIN_EMAIL, "password": "wrong"})
print(f"  POST /auth/login (password incorrecto) -> {r.status_code}")
if r.status_code == 401:
    ok("401 devuelto para credenciales invalidas")
else:
    fail(f"Esperaba 401, recibio {r.status_code}")

r = client.get(f"{BASE}/admin/conjuntos")
print(f"  GET /admin/conjuntos sin token -> {r.status_code}")
if r.status_code == 401:
    ok("401 sin token OK")
else:
    fail(f"Esperaba 401, recibio {r.status_code}")

r = client.get(f"{BASE}/admin/conjuntos", headers={"Authorization": "Bearer token_falso"})
print(f"  GET /admin/conjuntos token falso -> {r.status_code}")
if r.status_code == 401:
    ok("401 con token falso OK")
else:
    fail(f"Esperaba 401, recibio {r.status_code}")


# 3. CONJUNTOS
sep("3. CONJUNTOS - CRUD SuperAdmin")

r = client.get(f"{BASE}/admin/conjuntos", headers=HDR)
print(f"  GET /admin/conjuntos -> {r.status_code}")
if r.status_code == 200:
    ok(f"Lista OK - {len(r.json())} conjuntos existentes")
else:
    fail(f"ERROR: {r.text}")

payload = {
    "nombre": "Conjunto Prueba Test",
    "nit": "900123456-1",
    "direccion": "Calle 123 # 45-67",
    "ciudad": "Bogota"
}
r = client.post(f"{BASE}/admin/conjuntos", json=payload, headers=HDR)
print(f"  POST /admin/conjuntos -> {r.status_code}")
if r.status_code == 201:
    conjunto = r.json()
    CONJUNTO_ID = conjunto["id"]
    ok(f"Conjunto creado: id={CONJUNTO_ID[:8]}... nombre={conjunto['nombre']}")
else:
    fail(f"ERROR: {r.text}")
    sys.exit(1)

r = client.post(f"{BASE}/admin/conjuntos", json=payload, headers=HDR)
print(f"  POST /admin/conjuntos (duplicado) -> {r.status_code}")
if r.status_code == 409:
    ok("409 devuelto para nombre duplicado")
else:
    fail(f"Esperaba 409, recibio {r.status_code}: {r.text}")

r = client.get(f"{BASE}/admin/conjuntos/{CONJUNTO_ID}", headers=HDR)
print(f"  GET /admin/conjuntos/id -> {r.status_code}")
if r.status_code == 200:
    ok(f"Detalle OK: {r.json()['nombre']}")
else:
    fail(f"ERROR: {r.text}")

r = client.put(f"{BASE}/admin/conjuntos/{CONJUNTO_ID}", json={"ciudad": "Medellin"}, headers=HDR)
print(f"  PUT /admin/conjuntos/id -> {r.status_code}")
if r.status_code == 200:
    ok(f"Editado OK - ciudad={r.json()['ciudad']}")
else:
    fail(f"ERROR: {r.text}")

r = client.get(f"{BASE}/admin/conjuntos/00000000-0000-0000-0000-000000000000", headers=HDR)
print(f"  GET /admin/conjuntos/00000000 (inexistente) -> {r.status_code}")
if r.status_code == 404:
    ok("404 correctamente devuelto")
else:
    fail(f"Esperaba 404, recibio {r.status_code}")

r = client.post(f"{BASE}/admin/conjuntos", json={}, headers=HDR)
print(f"  POST /admin/conjuntos sin nombre (Pydantic) -> {r.status_code}")
if r.status_code == 422:
    ok("422 validacion Pydantic OK")
else:
    fail(f"Esperaba 422, recibio {r.status_code}")


# 4. CONFIGURACION
sep("4. CONFIGURACION")
print("  [NOTA] /api/configuracion requiere usuario con conjunto asignado via middleware.")
print("         El conjunto creado ya tiene ConfiguracionConjunto por defecto.")
print("         Se probara con usuario de conjunto en pruebas de integracion.")


# 5. SUSCRIPCIONES
sep("5. SUSCRIPCIONES - SuperAdmin")

r = client.put(f"{BASE}/admin/suscripciones/{CONJUNTO_ID}/suspender", json={}, headers=HDR)
print(f"  PUT .../suspender (sin suscripcion) -> {r.status_code}")
if r.status_code == 404:
    ok("404 devuelto - sin suscripcion")
else:
    fail(f"Esperaba 404, recibio {r.status_code}: {r.text}")

r = client.get(f"{BASE}/admin/suscripciones", headers=HDR)
print(f"  GET /admin/suscripciones -> {r.status_code}")
if r.status_code == 200:
    ok(f"Lista OK - {len(r.json())} suscripciones")
else:
    fail(f"ERROR: {r.text}")


# 6. PROPIEDADES
sep("6. PROPIEDADES - SuperAdmin bypass")
r = client.get(f"{BASE}/api/propiedades", headers=HDR)
print(f"  GET /api/propiedades (superadmin) -> {r.status_code}")
if r.status_code == 200:
    ok(f"SuperAdmin accede via bypass - {len(r.json())} propiedades")
else:
    print(f"  [INFO] {r.status_code}: {r.text[:120]}")


# 7. CLEANUP
sep("7. CLEANUP - eliminar conjunto de prueba")
r = client.delete(f"{BASE}/admin/conjuntos/{CONJUNTO_ID}", headers=HDR)
print(f"  DELETE /admin/conjuntos/id -> {r.status_code}")
if r.status_code == 204:
    ok("Soft delete OK")
else:
    fail(f"ERROR: {r.text}")

r = client.get(f"{BASE}/admin/conjuntos", headers=HDR)
ids_activos = [c["id"] for c in r.json()]
if CONJUNTO_ID not in ids_activos:
    ok("Conjunto eliminado no aparece en la lista")
else:
    fail("El conjunto eliminado sigue apareciendo")

r = client.get(f"{BASE}/admin/conjuntos/{CONJUNTO_ID}", headers=HDR)
if r.status_code == 404:
    ok("GET al eliminado devuelve 404")
else:
    fail(f"Esperaba 404, recibio {r.status_code}")

client.close()

print("\n" + "="*55)
print("PRUEBAS COMPLETADAS")
print("="*55)
