from fastapi import Request
from slowapi import Limiter


def _rate_limit_key(request: Request) -> str:
    """Ключ лимита: реальный IP клиента за доверенным прокси (X-Forwarded-For)."""
    xff = request.headers.get("x-forwarded-for", "")
    if xff:
        return xff.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


# Общий лимитер для всех эндпоинтов приложения.
limiter = Limiter(key_func=_rate_limit_key)