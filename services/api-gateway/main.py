from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import Response
from fastapi.middleware.cors import CORSMiddleware
import httpx
import requests
import logging
import time
import uuid

from config import JWKS_URL
from auth import verify_jwt

app = FastAPI()

# =========================
# LOGGING
# =========================
logging.basicConfig(level=logging.INFO)

# =========================
# CORS CONFIGURATION
# =========================
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 🔥 बदल to your frontend domain in production
    allow_credentials=False,  # must be False when using "*"
    allow_methods=["*"],
    allow_headers=["*"],
)

# =========================
# SERVICE MAPPING (K8s DNS)
# =========================
SERVICE_MAP = {
    "products": "http://product:8001",
    "cart": "http://cart:8002",
    "users": "http://user:8003",
    "orders": "http://order:8004",
}

# Public routes (no auth)
PUBLIC_ROUTES = ["products"]

# =========================
# JWKS CACHE (COGNITO SAFE)
# =========================
jwks_cache = {
    "data": None,
    "last_fetch": 0
}

def get_jwks():
    if time.time() - jwks_cache["last_fetch"] > 3600:
        jwks_cache["data"] = requests.get(JWKS_URL).json()
        jwks_cache["last_fetch"] = time.time()
    return jwks_cache["data"]

# =========================
# HEALTH CHECK
# =========================
@app.get("/health")
def health():
    return {"status": "ok"}

# =========================
# ROOT ROUTE HANDLER
# =========================
@app.api_route("/api/{service}", methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"])
async def gateway_root(service: str, request: Request):
    return await gateway(service, "", request)

# =========================
# MAIN GATEWAY ROUTE
# =========================
@app.api_route("/api/{service}/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"])
async def gateway(service: str, path: str, request: Request):

    # =========================
    # HANDLE PREFLIGHT (CORS)
    # =========================
    if request.method == "OPTIONS":
        return Response(
            status_code=204,
            headers={
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "*",
                "Access-Control-Allow-Headers": "*",
            },
        )

    # =========================
    # SERVICE VALIDATION
    # =========================
    base_url = SERVICE_MAP.get(service)
    if not base_url:
        raise HTTPException(status_code=404, detail="Service not found")

    # =========================
    # AUTH CHECK
    # =========================
    if service not in PUBLIC_ROUTES:
        verify_jwt(request)

    # =========================
    # BUILD TARGET URL
    # =========================
    clean_path = path.strip("/") if path else ""
    url = f"{base_url}/{clean_path}" if clean_path else f"{base_url}/"

    # Preserve query params
    if request.url.query:
        url = f"{url}?{request.url.query}"

    # =========================
    # REQUEST ID (TRACE)
    # =========================
    request_id = str(uuid.uuid4())
    logging.info(f"{request_id} | {request.method} → {url}")

    # =========================
    # HEADERS FORWARDING
    # =========================
    headers = {
        k: v for k, v in request.headers.items()
        if k.lower() not in ["host", "content-length", "connection"]
    }

    # Preserve Authorization header
    if "authorization" in request.headers:
        headers["authorization"] = request.headers["authorization"]

    # Add request ID header
    headers["x-request-id"] = request_id

    # =========================
    # FORWARD REQUEST (RETRY)
    # =========================
    try:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(5.0, connect=2.0)
        ) as client:

            for attempt in range(2):  # retry once
                try:
                    resp = await client.request(
                        method=request.method,
                        url=url,
                        headers=headers,
                        content=await request.body(),
                    )
                    break
                except httpx.RequestError as e:
                    if attempt == 1:
                        raise e

        return Response(
            content=resp.content,
            status_code=resp.status_code,
            headers=dict(resp.headers),  # preserve all headers
        )

    except httpx.RequestError as e:
        logging.error(f"{request_id} | Service call failed: {str(e)}")
        raise HTTPException(status_code=502, detail="Service unavailable")
