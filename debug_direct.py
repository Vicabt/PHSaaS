import httpx

# Login
r1 = httpx.post("http://localhost:8000/auth/login",
               json={"email":"vccompany011@email.com","password":"Vc92985315$%"},
               timeout=30)
token = r1.json()["data"]["access_token"]
print("Token:", token[:50], "...")

HDR = {"Authorization": f"Bearer {token}"}

# /auth/me
r2 = httpx.get("http://localhost:8000/auth/me", headers=HDR, timeout=30)
print("/auth/me:", r2.status_code)

# /admin/conjuntos
r3 = httpx.get("http://localhost:8000/admin/conjuntos", headers=HDR, timeout=30)
print("/admin/conjuntos:", r3.status_code, r3.text[:200])
