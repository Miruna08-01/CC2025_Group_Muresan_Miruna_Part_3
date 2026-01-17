import os
import requests
from fastapi import HTTPException, Request
from jose import jwt, JWTError

COGNITO_ISSUER = os.getenv("COGNITO_ISSUER")
COGNITO_CLIENT_ID = os.getenv("COGNITO_CLIENT_ID")

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
    for k in jwks["keys"]:
        if k["kid"] == kid:
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
        raise HTTPException(status_code=401, detail=f"Invalid token: {str(e)}")


def require_auth(request: Request) -> dict:
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing Bearer token")

    token = auth_header.split(" ", 1)[1]
    payload = verify_cognito_token(token)

    groups = payload.get("cognito:groups", [])
    role = groups[0] if isinstance(groups, list) and groups else (groups or "user")

    user = {
        "email": payload.get("email"),
        "sub": payload.get("sub"),
        "role": role,
        "device_id": payload.get("custom:device_id"),
    }

    # auth/security logs
    print("AUTH_OK", user)
    return user
