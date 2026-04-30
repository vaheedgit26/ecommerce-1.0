```python
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

# सार्वजनिक routes (no auth required)
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

    # ✅ Build target URL (with query params)
    query = request.url.query
    url = f"{base_url}/{path}" if path else f"{base_url}/"

    if query:
        url = f"{url}?{query}"

    # Debug logging
    logging.info(f"{request.method} → {url}")

    # ✅ Clean headers (remove problematic ones)
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

        # ✅ Return raw response (no JSON corruption)
        return Response(
            content=resp.content,
            status_code=resp.status_code,
            media_type=resp.headers.get("content-type")
        )

    except httpx.RequestError as e:
        logging.error(f"Service call failed: {str(e)}")
        raise HTTPException(status_code=502, detail="Service unavailable")
```
