import hmac

from fastapi import Header, HTTPException, status

from app.core.config import get_settings


def verify_device_key(x_device_key: str | None = Header(default=None)) -> None:
    """Require the configured device key when production authentication is enabled."""
    settings = get_settings()
    if not settings.REQUIRE_INGEST_AUTH:
        return
    if not settings.INGEST_API_KEY or not x_device_key or not hmac.compare_digest(
        x_device_key, settings.INGEST_API_KEY
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid device credentials",
            headers={"WWW-Authenticate": "ApiKey"},
        )
