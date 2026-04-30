import os

AWS_REGION = os.getenv("AWS_REGION", "ap-south-1")
USER_POOL_ID = os.getenv("USER_POOL_ID", "your_user_pool_id")
APP_CLIENT_ID = os.getenv("APP_CLIENT_ID", "your_app_client_id")

COGNITO_ISSUER = f"https://cognito-idp.{AWS_REGION}.amazonaws.com/{USER_POOL_ID}"
JWKS_URL = f"{COGNITO_ISSUER}/.well-known/jwks.json"
