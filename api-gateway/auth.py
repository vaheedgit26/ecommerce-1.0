from fastapi import HTTPException, Request
from jose import jwt
import requests
import time
from config import JWKS_URL, COGNITO_ISSUER, APP_CLIENT_ID


# =========================
# JWKS CACHE (TTL BASED)
# =========================
_jwks_cache = None
_jwks_cache_time = 0
JWKS_TTL_SECONDS = 3600  # 1 hour


def get_jwks():
    """
    Fetch JWKS from Cognito with caching.
    Prevents hitting AWS on every request.
    """
    global _jwks_cache, _jwks_cache_time

    now = time.time()

    # ✅ Return cached JWKS if valid
    if _jwks_cache and (now - _jwks_cache_time) < JWKS_TTL_SECONDS:
        return _jwks_cache

    # ❌ Fetch fresh JWKS
    response = requests.get(JWKS_URL)
    response.raise_for_status()

    _jwks_cache = response.json()
    _jwks_cache_time = now

    return _jwks_cache


def get_public_key(token):
    """
    Get signing key for JWT.
    Includes auto-refresh-on-failure retry logic.
    """

    def find_key(jwks, kid):
        for key in jwks["keys"]:
            if key["kid"] == kid:
                return key
        return None

    # First attempt
    jwks = get_jwks()
    headers = jwt.get_unverified_header(token)
    kid = headers.get("kid")

    key = find_key(jwks, kid)
    if key:
        return key

    # =========================
    # AUTO REFRESH ON FAILURE
    # =========================
    global _jwks_cache, _jwks_cache_time

    _jwks_cache = None
    _jwks_cache_time = 0

    jwks = get_jwks()

    key = find_key(jwks, kid)
    if key:
        return key

    raise HTTPException(status_code=401, detail="Invalid token key")


def verify_jwt(request: Request):
    """
    Validate Cognito JWT from Authorization header.
    """

    auth_header = request.headers.get("Authorization")

    if not auth_header:
        raise HTTPException(status_code=401, detail="Missing token")

    # Safe parsing
    parts = auth_header.split()
    if len(parts) != 2:
        raise HTTPException(status_code=401, detail="Invalid token format")

    token = parts[1]

    try:
        key = get_public_key(token)

        payload = jwt.decode(
            token,
            key,
            algorithms=["RS256"],
            issuer=COGNITO_ISSUER,
            audience=APP_CLIENT_ID,
        )

        return payload

    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {str(e)}")
