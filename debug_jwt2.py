import httpx, json, base64
from jose import jwk, jwt, JWTError

SUPABASE_URL = "https://lksaslnxnlcyxsemkbml.supabase.co"

# 1. Login
r = httpx.post("http://localhost:8000/auth/login",
               json={"email":"vccompany011@email.com","password":"Vc92985315$%"},
               timeout=30)
token = r.json()["data"]["access_token"]
print("[1] Token obtenido OK")

# 2. Obtener JWKS
r2 = httpx.get(f"{SUPABASE_URL}/auth/v1/.well-known/jwks.json", timeout=10)
jwks = r2.json()
print("[2] JWKS obtenido, keys:", len(jwks.get("keys",[])))

# 3. Buscar kid
header = jwt.get_unverified_header(token)
kid = header.get("kid")
key_data = next((k for k in jwks["keys"] if k.get("kid") == kid), None)
print("[3] key_data encontrado:", key_data is not None)
if key_data:
    print("    key type:", key_data.get("kty"), "alg:", key_data.get("alg"))

# 4. Construir clave y decodificar
try:
    public_key = jwk.construct(key_data)
    payload = jwt.decode(token, public_key, algorithms=["ES256"], options={"verify_aud": False})
    print("[4] Decode OK, sub:", payload.get("sub"))
except Exception as e:
    print("[4] ERROR:", type(e).__name__, ":", str(e))

# 5. Intentar con options={"verify_aud":False, "verify_iss":False}
try:
    public_key2 = jwk.construct(key_data)
    payload2 = jwt.decode(token, public_key2, algorithms=["ES256"], options={"verify_aud": False, "verify_iss": False})
    print("[5] Decode con verify_iss=False OK, sub:", payload2.get("sub"))
except Exception as e:
    print("[5] ERROR:", type(e).__name__, ":", str(e))
