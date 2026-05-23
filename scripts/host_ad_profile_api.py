"""
HTTP API on Windows host: real AD profile for Docker (no keytab).
GET http://127.0.0.1:18080/profile/<login>
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer

_PORT = int(os.environ.get("AD_HOST_API_PORT", "18080"))
_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
_PS1 = os.path.join(_ROOT, "scripts", "get-ad-user-json.ps1")
_LOGIN_RE = re.compile(r"^[a-z0-9._-]{1,128}$")


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

    def do_GET(self):
        if not self.path.startswith("/profile/"):
            self.send_error(404)
            return
        login = self.path.split("/profile/", 1)[-1].split("?", 1)[0].strip().lower()
        if not login or not _LOGIN_RE.fullmatch(login):
            self.send_error(400)
            return
        try:
            proc = subprocess.run(
                [
                    "powershell.exe",
                    "-NoLogo",
                    "-NoProfile",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-File",
                    _PS1,
                    login,
                ],
                capture_output=True,
                text=True,
                timeout=60,
                cwd=_ROOT,
            )
        except Exception as ex:
            self.send_error(500, str(ex))
            return
        if proc.returncode != 0:
            self.send_error(404, proc.stderr or "AD lookup failed")
            return
        try:
            payload = json.loads(proc.stdout.strip() or "{}")
        except json.JSONDecodeError:
            self.send_error(500, "invalid json from AD")
            return
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main():
    if sys.platform != "win32":
        print("host_ad_profile_api.py only runs on Windows host", file=sys.stderr)
        sys.exit(1)
    server = HTTPServer(("127.0.0.1", _PORT), Handler)
    print(f"AD host API http://127.0.0.1:{_PORT}/profile/<login>")
    server.serve_forever()


if __name__ == "__main__":
    main()
