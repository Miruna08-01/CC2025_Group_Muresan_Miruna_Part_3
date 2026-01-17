import os
import requests
from fastapi import HTTPException, Request
from jose import jwt, JWTError

COGNITO_ISSUER = os.getenv("COGNITO_ISSUER")
COGNITO_CLIENT_ID = os.getenv("COGNITO_CLIENT_ID")

if not COGNITO_ISSUER or not COGNITO_CLIENT_ID:
    raise RuntimeError("Missing COGNITO_ISSUER or COGNITO_CLIENT_ID env vars")

_jwks_cache = None

def get_jwks():
    global _jwks_cache
    if _jwks_cache is None:
        url = f"{COGNITO_ISSUER}/.well-known/jwks.json"
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        _jwks_cache = r.json()
    return _jwks_cache

def verify_cognito_token(token: str) -> dict:
    jwks = get_jwks()
    headers = jwt.get_unverified_header(token)
    kid = headers.get("kid")

    key = None
    for k in jwks.get("keys", []):
        if k.get("kid") == kid:
            key = k
            break
    if not key:
        raise HTTPException(status_code=401, detail="Invalid token key (kid not found)")

    try:
        payload = jwt.decode(
            token,
            key,
            algorithms=["RS256"],
            audience=COGNITO_CLIENT_ID,
            issuer=COGNITO_ISSUER,
            options={"verify_at_hash": False},
        )
        return payload
    except JWTError as e:
        raise HTTPException(status_code=401, detail=f"Invalid or expired token: {str(e)}")

def require_auth(request: Request) -> dict:
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        print("[AUTH] Missing Bearer token")
        raise HTTPException(status_code=401, detail="Missing Authorization: Bearer <token>")

    token = auth.split(" ", 1)[1]
    payload = verify_cognito_token(token)

    groups = payload.get("cognito:groups", []) or []
    role = "admin" if "admin" in groups else ("user" if "user" in groups else "unknown")
    device_id = payload.get("custom:device_id")

    user = {
        "email": payload.get("email"),
        "sub": payload.get("sub"),
        "role": role,
        "device_id": device_id,
    }

    print("[AUTH_OK]", user)
    return user
