#!/usr/bin/env python3
import os
from pathlib import Path


def load_env(env_path: Path) -> None:
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s or s.startswith("#") or "=" not in s:
            continue
        key, val = s.split("=", 1)
        key = key.strip()
        val = val.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = val


def render_template(text: str, mapping: dict) -> str:
    out = text
    for key, value in mapping.items():
        out = out.replace(f"__{key}__", value)
    return out


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    load_env(root / ".env")

    namespace = os.getenv("K8S_NAMESPACE", "kerberos-sso")
    hostname = os.getenv("K8S_HOSTNAME", os.getenv("SPN_HOSTNAME", "app.example.com"))
    image = os.getenv("IMAGE", "ghcr.io/your-org/kerberos-sso:latest")
    ldap_uri = os.getenv("LDAP_URI", "ldap://dc01.example.com")
    ldap_base_dn = os.getenv("LDAP_BASE_DN", "DC=example,DC=com")
    realm = os.getenv("KERBEROS_REALM", "EXAMPLE.COM")
    service_name = os.getenv("KERBEROS_SERVICE_NAME", "HTTP")
    log_level = os.getenv("LOG_LEVEL", "INFO")

    generated_dir = root / "k8s" / "generated"
    generated_dir.mkdir(parents=True, exist_ok=True)

    mapping = {
        "NAMESPACE": namespace,
        "HOSTNAME": hostname,
        "IMAGE": image,
        "LDAP_URI": ldap_uri,
        "LDAP_BASE_DN": ldap_base_dn,
        "KERBEROS_REALM": realm,
        "KERBEROS_SERVICE_NAME": service_name,
        "LOG_LEVEL": log_level,
    }

    for name in ("namespace", "configmap", "redis", "service", "ingress", "deployment"):
        src = root / "k8s" / f"{name}.template.yaml"
        dst = generated_dir / f"{name}.yaml"
        text = src.read_text(encoding="utf-8")
        dst.write_text(render_template(text, mapping), encoding="utf-8")
        print(f"rendered: {dst}")


if __name__ == "__main__":
    main()
