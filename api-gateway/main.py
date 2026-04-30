from fastapi import FastAPI, Request, HTTPException
import httpx
from auth import verify_jwt

app = FastAPI()

# Service mapping (Kubernetes service names)
SERVICE_MAP = {
    "products": "http://product-service",
    "cart": "http://cart-service",
    "user": "http://user-service",
    "order": "http://order-service",
}

# Health check
@app.get("/health")
def health():
    return {"status": "ok"}

# Main gateway route
# @app.api_route("/{service}/{path:path}", methods=["GET", "POST", "PUT", "DELETE"])
@app.api_route("/api/{service}/{path:path}", methods=["GET", "POST", "PUT", "DELETE"])
async def gateway(service: str, path: str, request: Request):
    base_url = SERVICE_MAP.get(service)

    if not base_url:
        raise HTTPException(status_code=404, detail="Service not found")

    # 🔐 Protect all except products
    # if service != "products":
    #    verify_jwt(request)

    PUBLIC_ROUTES = ["products"]

    if service not in PUBLIC_ROUTES:
        verify_jwt(request)

    url = f"{base_url}/{path}"

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.request(
                method=request.method,
                url=url,
                headers=dict(request.headers),
                content=await request.body()
            )

        return response.json()

    except httpx.RequestError:
        raise HTTPException(status_code=502, detail="Service unavailable")
