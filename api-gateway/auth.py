from fastapi import HTTPException, Request
from jose import jwt
import requests
from config import JWKS_URL, COGNITO_ISSUER, APP_CLIENT_ID

jwks = requests.get(JWKS_URL).json()

def get_public_key(token):
    headers = jwt.get_unverified_header(token)
    kid = headers.get("kid")

    for key in jwks["keys"]:
        if key["kid"] == kid:
            return key

    raise HTTPException(status_code=401, detail="Invalid token key")

def verify_jwt(request: Request):
    auth_header = request.headers.get("Authorization")

    if not auth_header:
        raise HTTPException(status_code=401, detail="Missing token")

    token = auth_header.split(" ")[1]

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
