from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import Response
import httpx
from auth import verify_jwt
import logging

app = FastAPI()

# Logging
logging.basicConfig(level=logging.INFO)

# Kubernetes service mapping
SERVICE_MAP = {
    "products": "http://product-service",
    "cart": "http://cart-service",
    "users": "http://user-service",
    "orders": "http://order-service"
}

# Public routes (no auth required)
PUBLIC_ROUTES = ["products"]

# Health check
@app.get("/health")
def health():
    return {"status": "ok"}


@app.api_route("/api/{service}/{path:path}", methods=["GET", "POST", "PUT", "DELETE"])
async def gateway(service: str, path: str, request: Request):

    base_url = SERVICE_MAP.get(service)

    if not base_url:
        raise HTTPException(status_code=404, detail="Service not found")

    # 🔐 Authentication
    if service not in PUBLIC_ROUTES:
        verify_jwt(request)

    # ✅ Normalize path (handle trailing slashes safely)
    clean_path = path.strip("/") if path else ""

    if clean_path:
        url = f"{base_url}/{service}/{clean_path}"
    else:
        url = f"{base_url}/{service}"

    # ✅ Preserve query params
    query = request.url.query
    if query:
        url = f"{url}?{query}"

    # Debug logging
    logging.info(f"{request.method} → {url}")

    # ✅ Clean headers
    headers = {
        k: v for k, v in request.headers.items()
        if k.lower() not in ["host", "content-length", "connection"]
    }

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

        # ✅ Return raw response
        return Response(
            content=resp.content,
            status_code=resp.status_code,
            media_type=resp.headers.get("content-type")
        )

    except httpx.RequestError as e:
        logging.error(f"Service call failed: {str(e)}")
        raise HTTPException(status_code=502, detail="Service unavailable")
