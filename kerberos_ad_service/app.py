import base64
import json
import logging
import os
import subprocess
import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from flask import Flask, jsonify, request
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from ldap3 import ALL, Connection, SASL, Server
from ldap3.core.exceptions import LDAPException
from ldap3.utils.conv import escape_filter_chars
from prometheus_client import Counter, CONTENT_TYPE_LATEST, generate_latest
from sqlalchemy import JSON, Column, DateTime, Integer, MetaData, String, create_engine
from sqlalchemy.orm import Session, declarative_base, sessionmaker
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_fixed

from config import Settings

try:
    import spnego
except ImportError:  # pragma: no cover
    spnego = None


AUTH_SUCCESS = Counter("auth_success_total", "Successful Kerberos authentications")
AUTH_FAILURE = Counter("auth_failure_total", "Failed Kerberos authentications")
LDAP_SUCCESS = Counter("ldap_success_total", "Successful LDAP lookups")
LDAP_FAILURE = Counter("ldap_failure_total", "Failed LDAP lookups")


def configure_logging(settings: Settings) -> None:
    class JsonFormatter(logging.Formatter):
        def format(self, record: logging.LogRecord) -> str:
            payload = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "level": record.levelname,
                "logger": record.name,
                "message": record.getMessage(),
            }
            if hasattr(record, "event"):
                payload["event"] = record.event
            if hasattr(record, "username"):
                payload["username"] = record.username
            if record.exc_info:
                payload["exc_info"] = self.formatException(record.exc_info)
            return json.dumps(payload, ensure_ascii=True)

    root = logging.getLogger()
    root.setLevel(settings.log_level.upper())
    root.handlers.clear()
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    root.addHandler(handler)


metadata = MetaData()
Base = declarative_base(metadata=metadata)


class UserEvent(Base):
    __tablename__ = "user_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(120), nullable=False, index=True)
    principal = Column(String(256), nullable=False)
    ad_payload = Column(JSON, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class UserRepository:
    def __init__(self, database_url: str):
        self.engine = create_engine(database_url, future=True, pool_pre_ping=True)
        self._session = sessionmaker(bind=self.engine, expire_on_commit=False, future=True)
        Base.metadata.create_all(self.engine)

    def save_event(self, username: str, principal: str, ad_payload: Dict[str, Any]) -> None:
        with self._session() as session:
            self._save(session, username, principal, ad_payload)

    def healthcheck(self) -> None:
        with self.engine.connect() as conn:
            conn.exec_driver_sql("SELECT 1")

    @staticmethod
    def _save(session: Session, username: str, principal: str, ad_payload: Dict[str, Any]) -> None:
        session.add(UserEvent(username=username, principal=principal, ad_payload=ad_payload))
        session.commit()


class KerberosAuthenticator:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.logger = logging.getLogger(self.__class__.__name__)

    def authenticate(self, authorization_header: Optional[str]) -> Dict[str, str]:
        if not authorization_header or not authorization_header.startswith("Negotiate "):
            raise ValueError("Missing Negotiate header")
        if spnego is None:
            raise RuntimeError("pyspnego is not installed")

        token_b64 = authorization_header.split(" ", 1)[1]
        server_ctx = spnego.server(hostname=os.getenv("SPN_HOSTNAME"))
        in_token = base64.b64decode(token_b64)
        server_ctx.step(in_token)
        principal = server_ctx.client_principal or ""
        if not principal or "@" not in principal:
            raise ValueError("Kerberos token does not contain principal")
        username = principal.split("@", 1)[0]
        return {"username": username, "principal": principal}

    def healthcheck(self) -> None:
        if not os.path.exists(self.settings.kerberos_keytab):
            raise FileNotFoundError(f"Keytab not found: {self.settings.kerberos_keytab}")
        if self.settings.kerberos_verify_kinit:
            self._run_kinit_check()

    def _run_kinit_check(self) -> None:
        principal = f"{self.settings.kerberos_service_name}/{os.getenv('SPN_HOSTNAME', 'localhost')}@{self.settings.kerberos_realm}"
        cmd = [
            "kinit",
            "-k",
            "-t",
            self.settings.kerberos_keytab,
            principal,
        ]
        subprocess.run(cmd, check=True, timeout=self.settings.kerberos_kinit_timeout_s, capture_output=True, text=True)


class ADClient:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.logger = logging.getLogger(self.__class__.__name__)

    def fetch_user(self, sam_account_name: str) -> Dict[str, Any]:
        safe_login = escape_filter_chars((sam_account_name or "").strip(), encoding="utf-8")
        if not safe_login:
            raise ValueError("sAMAccountName is empty after sanitization")

        @retry(
            retry=retry_if_exception_type(LDAPException),
            stop=stop_after_attempt(self.settings.ldap_retry_attempts),
            wait=wait_fixed(self.settings.ldap_retry_delay_s),
            reraise=True,
        )
        def _lookup() -> Dict[str, Any]:
            server = Server(
                host=self.settings.ldap_uri,
                get_info=ALL,
                connect_timeout=self.settings.ldap_connect_timeout_s,
            )
            conn = Connection(
                server=server,
                authentication=SASL,
                sasl_mechanism="GSSAPI",
                auto_bind=True,
                receive_timeout=self.settings.ldap_read_timeout_s,
            )
            search_filter = f"(&(objectClass=user)(sAMAccountName={safe_login}))"
            conn.search(
                search_base=self.settings.ldap_base_dn,
                search_filter=search_filter,
                attributes=["sAMAccountName", "displayName", "mail", "department", "title"],
            )
            if not conn.entries:
                raise LookupError(f"User not found in AD: {sam_account_name}")
            entry = conn.entries[0]
            return {
                "sAMAccountName": str(entry.sAMAccountName.value or ""),
                "displayName": str(entry.displayName.value or ""),
                "mail": str(entry.mail.value or ""),
                "department": str(entry.department.value or ""),
                "title": str(entry.title.value or ""),
            }

        return _lookup()

    def healthcheck(self) -> None:
        # Fast TCP-level check only, to keep /health light.
        server = Server(host=self.settings.ldap_uri, get_info=None, connect_timeout=2)
        conn = Connection(server=server, authentication=SASL, sasl_mechanism="GSSAPI", raise_exceptions=True)
        conn.bind()


def create_app(settings: Optional[Settings] = None) -> Flask:
    settings = settings or Settings()
    configure_logging(settings)
    app = Flask(__name__)
    app.config["JSON_SORT_KEYS"] = False
    app.config["DEBUG"] = False if settings.is_prod else settings.debug

    limiter = Limiter(
        get_remote_address,
        app=app,
        default_limits=[settings.rate_limit_default],
        storage_uri=settings.rate_limit_storage_uri,
    )
    repo = UserRepository(settings.database_url)
    kerberos = KerberosAuthenticator(settings)
    ad_client = ADClient(settings)
    logger = logging.getLogger("sso-app")

    if settings.otel_enabled:
        logger.info("OpenTelemetry integration can be wired via OTLP env vars")

    @app.route("/auth/me", methods=["GET"])
    @limiter.limit(settings.rate_limit_auth)
    def auth_me():
        started = time.perf_counter()
        auth_header = request.headers.get("Authorization")
        try:
            principal_data = kerberos.authenticate(auth_header)
            AUTH_SUCCESS.inc()
            LDAP_SUCCESS.inc()
            ad_payload = ad_client.fetch_user(principal_data["username"])
            repo.save_event(principal_data["username"], principal_data["principal"], ad_payload)
            logger.info(
                "Authentication and AD lookup succeeded",
                extra={"event": "auth_success", "username": principal_data["username"]},
            )
            return jsonify(
                {
                    "status": "ok",
                    "username": principal_data["username"],
                    "principal": principal_data["principal"],
                    "ad_user": ad_payload,
                    "duration_ms": int((time.perf_counter() - started) * 1000),
                }
            )
        except Exception as exc:  # pylint: disable=broad-except
            AUTH_FAILURE.inc()
            LDAP_FAILURE.inc()
            logger.exception("Authentication pipeline failed", extra={"event": "auth_failure"})
            response = jsonify({"status": "error", "reason": str(exc)})
            response.status_code = 401
            response.headers["WWW-Authenticate"] = "Negotiate"
            return response

    @app.route("/health", methods=["GET"])
    def health():
        checks = {"kerberos": "ok", "ldap": "ok", "database": "ok"}
        try:
            kerberos.healthcheck()
            repo.healthcheck()
            ad_client.healthcheck()
            return jsonify({"status": "ok", "checks": checks}), 200
        except Exception as exc:  # pylint: disable=broad-except
            logger.exception("Health check failed", extra={"event": "health_failure"})
            return jsonify({"status": "degraded", "reason": str(exc), "checks": checks}), 503

    @app.route("/metrics", methods=["GET"])
    def metrics():
        return generate_latest(), 200, {"Content-Type": CONTENT_TYPE_LATEST}

    return app


if __name__ == "__main__":
    settings = Settings()
    flask_app = create_app(settings)
    flask_app.run(host=settings.host, port=settings.port, debug=False)
