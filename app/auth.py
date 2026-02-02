import secrets
from fastapi import Header, HTTPException

from app.config import API_KEY


def api_key_auth(x_api_key: str | None = Header(default=None, alias="x-api-key")) -> None:
    """
    FastAPI dependency for API key auth.
    - Reads header: x-api-key
    - Uses constant-time compare to prevent timing attacks.
    """
    print("Header",x_api_key)
    if not x_api_key:
        raise HTTPException(status_code=401, detail="Missing API key")

    if not secrets.compare_digest(x_api_key, API_KEY):
        raise HTTPException(status_code=401, detail="Invalid API key")
