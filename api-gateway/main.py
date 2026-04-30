from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import Response
from fastapi.middleware.cors import CORSMiddleware
import httpx
import requests
from auth import verify_jwt
import logging

app = FastAPI()

# Logging
logging.basicConfig(level=logging.INFO)

# =========================
# CORS CONFIGURATION
# =========================
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten to CloudFront domain in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =========================
# K8S SERVICE MAPPING
# =========================
SERVICE_MAP = {
    "products": "http://product-service",
    "cart": "http://cart-service",
    "users": "http://user-service",
    "orders": "http://order-service"
}

# Public routes
PUBLIC_ROUTES = ["products"]

# =========================
# COGNITO JWKS (SAFE FETCH)
# =========================
def get_jwks():
    return requests.get(JWKS_URL).json()

jwks = get_jwks()


# =========================
# HEALTH CHECK
# =========================
@app.get("/health")
def health():
    return {"status": "ok"}


# =========================
# ROOT ROUTE HANDLER
# =========================
@app.api_route("/api/{service}", methods=["GET", "POST", "PUT", "DELETE"])
async def gateway_root(service: str, request: Request):
    return await gateway(service, "", request)


# =========================
# MAIN GATEWAY ROUTE
# =========================
@app.api_route("/api/{service}/{path:path}", methods=["GET", "POST", "PUT", "DELETE"])
async def gateway(service: str, path: str, request: Request):

    base_url = SERVICE_MAP.get(service)

    if not base_url:
        raise HTTPException(status_code=404, detail="Service not found")

    # =========================
    # AUTH CHECK
    # =========================
    if service not in PUBLIC_ROUTES:
        verify_jwt(request)

    # =========================
    # BUILD TARGET URL (FIXED)
    # =========================
    clean_path = path.strip("/") if path else ""

    if clean_path:
        url = f"{base_url}/{clean_path}"
    else:
        url = f"{base_url}/"

    # Preserve query params
    query = request.url.query
    if query:
        url = f"{url}?{query}"

    # Logging
    logging.info(f"{request.method} → {url}")

    # =========================
    # HEADERS (SAFE FORWARDING)
    # =========================
    headers = {
        k: v for k, v in request.headers.items()
        if k.lower() not in ["host", "content-length", "connection"]
    }

    # Ensure Authorization is preserved
    headers["authorization"] = request.headers.get("authorization")

    # =========================
    # HTTP FORWARDING
    # =========================
    try:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(5.0, connect=2.0)
        ) as client:

            resp = await client.request(
                method=request.method,
                url=url,
                headers=headers,
                content=await request.body()
            )

        return Response(
            content=resp.content,
            status_code=resp.status_code,
            media_type=resp.headers.get("content-type")
        )

    except httpx.RequestError as e:
        logging.error(f"Service call failed: {str(e)}")
        raise HTTPException(status_code=502, detail="Service unavailable")
