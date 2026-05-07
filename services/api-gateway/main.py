from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import Response
from fastapi.middleware.cors import CORSMiddleware
import httpx
import logging
import uuid

from auth import verify_jwt

app = FastAPI()

# =========================
# LOGGING
# =========================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

# =========================
# CORS CONFIGURATION
# =========================
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # ⚠️ Change in production
    allow_credentials=False,
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
# HEALTH CHECK
# =========================
@app.get("/health")
def health():
    return {"status": "ok"}

# =========================
# ROOT ROUTE HANDLER
# =========================
@app.api_route("/api/{service}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def gateway_root(service: str, request: Request):
    return await gateway(service, "", request)

# =========================
# MAIN GATEWAY ROUTE
# =========================
@app.api_route("/api/{service}/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def gateway(service: str, path: str, request: Request):

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
    url = f"{base_url}/{clean_path}" if clean_path else base_url

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
    excluded_headers = {"host", "content-length", "connection"}

    headers = {
        k: v for k, v in request.headers.items()
        if k.lower() not in excluded_headers
    }

    headers["x-request-id"] = request_id

    # =========================
    # FORWARD REQUEST
    # =========================
    try:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(5.0, connect=2.0)
        ) as client:

            resp = await client.request(
                method=request.method,
                url=url,
                headers=headers,
                content=await request.body(),
            )

        # Remove problematic headers from downstream response
        response_headers = {
            k: v for k, v in resp.headers.items()
            if k.lower() not in {"content-encoding", "transfer-encoding", "connection"}
        }

        return Response(
            content=resp.content,
            status_code=resp.status_code,
            headers=response_headers,
        )

    except httpx.RequestError as e:
        logging.error(f"{request_id} | Service call failed: {str(e)}")
        raise HTTPException(status_code=502, detail="Service unavailable")
