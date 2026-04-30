from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import Response
import httpx
from auth import verify_jwt

app = FastAPI()

SERVICE_MAP = {
    "products": "http://product-service",
    "cart": "http://cart-service",
    "user": "http://user-service",
    "order": "http://order-service",
}

PUBLIC_ROUTES = ["products"]

@app.get("/health")
def health():
    return {"status": "ok"}

@app.api_route("/api/{service}/{path:path}", methods=["GET", "POST", "PUT", "DELETE"])
async def gateway(service: str, path: str, request: Request):

    base_url = SERVICE_MAP.get(service)

    if not base_url:
        raise HTTPException(status_code=404, detail="Service not found")

    # 🔐 Auth
    if service not in PUBLIC_ROUTES:
        verify_jwt(request)

    url = f"{base_url}/{path}" if path else base_url

    headers = {
        k: v for k, v in request.headers.items()
        if k.lower() not in ["host", "content-length"]
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
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

    except httpx.RequestError:
        raise HTTPException(status_code=502, detail="Service unavailable")
