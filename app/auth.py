import hmac

from fastapi import HTTPException

from app.config import CORTEX_INTERNAL_API_KEY


def require_internal_api_key(authorization: str | None) -> None:
    if not CORTEX_INTERNAL_API_KEY:
        raise HTTPException(status_code=503, detail="Internal Cortex API key is not configured")

    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")

    token = authorization.removeprefix("Bearer ").strip()
    if not token:
        raise HTTPException(status_code=401, detail="Missing bearer token")

    if not hmac.compare_digest(token, CORTEX_INTERNAL_API_KEY):
        raise HTTPException(status_code=403, detail="Invalid bearer token")
