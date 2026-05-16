from __future__ import annotations
import os
from backend import create_app

# WSGI entrypoint compatible with Gunicorn
# Используем FLASK_ENV из окружения (в Docker: testing с TEST_MODE=true)
env_name = os.environ.get("FLASK_ENV", "production")
application = create_app(env_name)

# Some servers look for `app`
app = application

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8000"))
    host = os.environ.get("HOST", "0.0.0.0")
    app.run(host=host, port=port)
