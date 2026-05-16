import os
from dataclasses import dataclass


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    app_env: str = os.getenv("APP_ENV", "dev")
    host: str = os.getenv("HOST", "0.0.0.0")
    port: int = int(os.getenv("PORT", "5000"))
    debug: bool = _env_bool("DEBUG", False)

    kerberos_service_name: str = os.getenv("KERBEROS_SERVICE_NAME", "HTTP")
    kerberos_realm: str = os.getenv("KERBEROS_REALM", "EXAMPLE.COM")
    kerberos_keytab: str = os.getenv("KERBEROS_KEYTAB", "/run/secrets/service_keytab")
    kerberos_verify_kinit: bool = _env_bool("KERBEROS_VERIFY_KINIT", True)
    kerberos_kinit_timeout_s: int = int(os.getenv("KERBEROS_KINIT_TIMEOUT_S", "5"))

    ldap_uri: str = os.getenv("LDAP_URI", "ldap://dc01.example.com")
    ldap_base_dn: str = os.getenv("LDAP_BASE_DN", "DC=example,DC=com")
    ldap_connect_timeout_s: int = int(os.getenv("LDAP_CONNECT_TIMEOUT_S", "5"))
    ldap_read_timeout_s: int = int(os.getenv("LDAP_READ_TIMEOUT_S", "5"))
    ldap_retry_attempts: int = int(os.getenv("LDAP_RETRY_ATTEMPTS", "3"))
    ldap_retry_delay_s: float = float(os.getenv("LDAP_RETRY_DELAY_S", "0.5"))

    database_url: str = os.getenv("DATABASE_URL", "sqlite:///users.db")

    request_timeout_s: int = int(os.getenv("REQUEST_TIMEOUT_S", "10"))
    rate_limit_default: str = os.getenv("RATE_LIMIT_DEFAULT", "30 per minute")
    rate_limit_auth: str = os.getenv("RATE_LIMIT_AUTH", "10 per minute")
    rate_limit_storage_uri: str = os.getenv("RATE_LIMIT_STORAGE_URI", "memory://")

    log_level: str = os.getenv("LOG_LEVEL", "INFO")
    prometheus_enabled: bool = _env_bool("PROMETHEUS_ENABLED", True)
    otel_enabled: bool = _env_bool("OTEL_ENABLED", False)

    @property
    def is_prod(self) -> bool:
        return self.app_env.lower() == "prod"
