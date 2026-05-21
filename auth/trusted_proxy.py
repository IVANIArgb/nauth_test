"""Проверка, что заголовки SSO приходят только от доверенного reverse-proxy."""
from __future__ import annotations

import ipaddress
import os
from typing import Optional


def _default_trusted_proxy_ips() -> str:
    base = "127.0.0.1,::1"
    if (os.environ.get("DOCKER") or "").strip():
        base += ",172.16.0.0/12,10.0.0.0/8"
    return base


def get_trusted_proxy_ips_spec() -> str:
    raw = (os.environ.get("TRUSTED_PROXY_IPS") or "").strip()
    if raw == "*":
        return "*"
    return raw or _default_trusted_proxy_ips()


def request_client_ip(remote_addr: Optional[str], x_forwarded_for: Optional[str]) -> str:
    """
    IP клиента для проверки доверия к SSO-заголовкам.
    Берём первый адрес из X-Forwarded-For (ближайший к прокси), иначе remote_addr.
    """
    if x_forwarded_for:
        first = x_forwarded_for.split(",")[0].strip()
        if first:
            return first
    return (remote_addr or "").strip()


def is_trusted_proxy_ip(
    client_ip: str,
    spec: Optional[str] = None,
) -> bool:
    """
    spec: список IP или CIDR через запятую; '*' — доверять всем (только dev/тесты).
    """
    spec = spec if spec is not None else get_trusted_proxy_ips_spec()
    if spec.strip() == "*":
        return True
    if not client_ip:
        return False
    try:
        addr = ipaddress.ip_address(client_ip)
    except ValueError:
        return False
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            if "/" in part:
                if addr in ipaddress.ip_network(part, strict=False):
                    return True
            elif addr == ipaddress.ip_address(part):
                return True
        except ValueError:
            continue
    return False
