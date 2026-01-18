import os
import json
from typing import Dict, Any
from dotenv import load_dotenv
import requests
from fastapi import Header, HTTPException
from jose import jwt, JWTError

load_dotenv()
COGNITO_ISSUER = os.getenv("COGNITO_ISSUER")
COGNITO_CLIENT_ID = os.getenv("COGNITO_CLIENT_ID")

if not COGNITO_ISSUER or not COGNITO_CLIENT_ID:
    raise RuntimeError("Missing COGNITO_ISSUER or COGNITO_CLIENT_ID env vars")

JWKS_URL = f"{COGNITO_ISSUER}/.well-known/jwks.json"

_jwks_cache: Dict[str, Any] | None = None


def _get_jwks() -> Dict[str, Any]:
    global _jwks_cache
    if _jwks_cache is None:
        resp = requests.get(JWKS_URL, timeout=10)
        resp.raise_for_status()
        _jwks_cache = resp.json()
    return _jwks_cache


def _extract_role_from_claims(claims: Dict[str, Any]) -> str:
    # Cognito: "cognito:groups" poate fi listă sau string
    groups = claims.get("cognito:groups", [])
    if isinstance(groups, list) and len(groups) > 0:
        return groups[0]
    if isinstance(groups, str) and groups:
        return groups
    return "user"


def require_auth(authorization: str = Header(None)) -> Dict[str, Any]:
    """
    Expects: Authorization: Bearer <JWT>
    Validates JWT with Cognito JWKS.
    Returns: {email, role, device_id, sub, raw_claims}
    """
    if not authorization:
        raise HTTPException(status_code=401, detail='Missing Authorization: Bearer <token>')

    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(status_code=401, detail="Invalid Authorization header format")

    token = parts[1]

    try:
        unverified_header = jwt.get_unverified_header(token)
        kid = unverified_header.get("kid")
        if not kid:
            raise HTTPException(status_code=401, detail="Invalid token header (missing kid)")

        jwks = _get_jwks()
        key = None
        for k in jwks.get("keys", []):
            if k.get("kid") == kid:
                key = k
                break
        if not key:
            raise HTTPException(status_code=401, detail="Signing key not found")

        claims = jwt.decode(
            token,
            key,
            algorithms=["RS256"],
            audience=COGNITO_CLIENT_ID,
            issuer=COGNITO_ISSUER,
            options={"verify_at_hash": False},
        )

        email = claims.get("email") or claims.get("cognito:username") or claims.get("username") or "unknown"
        role = _extract_role_from_claims(claims)

        # custom claim la tine e custom:device_id
        device_id = claims.get("custom:device_id") or claims.get("device_id")

        return {
            "email": email,
            "role": role,
            "device_id": device_id,
            "sub": claims.get("sub"),
            "raw_claims": claims,
        }

    except JWTError as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {str(e)}")
    except requests.RequestException as e:
        raise HTTPException(status_code=500, detail=f"JWKS fetch failed: {str(e)}")
