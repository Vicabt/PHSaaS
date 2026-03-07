import httpx, json, base64, time

r = httpx.post("http://localhost:8000/auth/login",
               json={"email":"vccompany011@email.com","password":"Vc92985315$%"},
               timeout=30)
print("Status:", r.status_code)
resp = r.json()
if r.status_code != 200:
    print("Error:", resp)
    exit(1)

token = resp["data"]["access_token"]

parts = token.split(".")
def b64d(s):
    s += "=" * (4 - len(s) % 4)
    return json.loads(base64.urlsafe_b64decode(s))

header = b64d(parts[0])
payload = b64d(parts[1])

now = int(time.time())
print("Header:", header)
print("iss:", payload.get("iss"))
print("aud:", payload.get("aud"))
print("app_metadata:", payload.get("app_metadata"))
print("exp:", payload.get("exp"))
print("iat:", payload.get("iat"))
print("now:", now)
print("exp - now:", payload.get("exp",0) - now, "seg")
