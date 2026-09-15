from ipaddress import ip_address, ip_network

from fastapi import Request
from slowapi import Limiter

from app.config import get_settings


def _is_trusted_proxy(host: str) -> bool:
    configured = get_settings().trusted_proxies
    try:
        address = ip_address(host)
    except ValueError:
        return False
    for item in configured.split(","):
        item = item.strip()
        if not item:
            continue
        try:
            if address in ip_network(item, strict=False):
                return True
        except ValueError:
            # Invalid configuration must fail closed rather than trusting a peer.
            continue
    return False


def _rate_limit_key(request: Request) -> str:
    """Ключ лимита: реальный IP клиента за доверенным прокси (X-Forwarded-For)."""
    peer = request.client.host if request.client else "unknown"
    xff = request.headers.get("x-forwarded-for", "")
    if xff and _is_trusted_proxy(peer):
        return xff.split(",")[0].strip()
    return peer


# Общий лимитер для всех эндпоинтов приложения.
limiter = Limiter(key_func=_rate_limit_key)
