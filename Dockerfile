# Multi-stage: сборка колёс в builder без утяжеления финального слоя gcc/lib*-dev.
FROM python:3.12-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DEFAULT_TIMEOUT=120 \
    PIP_RETRIES=10 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    gcc \
    libc6-dev \
    libkrb5-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements-prod.txt ./
ARG PIP_EXTRA_INDEX_URL=
RUN python -m pip install --upgrade pip setuptools wheel \
    && python -m venv /opt/venv \
    && . /opt/venv/bin/activate \
    && if [ -n "$PIP_EXTRA_INDEX_URL" ]; then \
         python -m pip install --retries 10 --timeout 120 \
           --extra-index-url "$PIP_EXTRA_INDEX_URL" -r requirements-prod.txt; \
       else \
         python -m pip install --retries 10 --timeout 120 -r requirements-prod.txt; \
       fi

# --- runtime ---
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONUTF8=1 \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8 \
    PATH="/opt/venv/bin:$PATH"

WORKDIR /app

ENV DEBIAN_FRONTEND=noninteractive
# Только runtime для Kerberos/GSSAPI (без *-dev)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    libkrb5-3 \
    libgssapi-krb5-2 \
    && update-ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /opt/venv /opt/venv

COPY . .

RUN mkdir -p backend/uploads backend/logs database \
    /app/categories-data /app/backups

ENV DOCKER=1 \
    FLASK_ENV=development \
    DOCKER_AUTH_FALLBACK=true \
    DOCKER_DEFAULT_USER=testadmin \
    HOST=0.0.0.0 \
    PORT=8000 \
    RUN_WITH_GUNICORN=true \
    GUNICORN_WORKERS=2 \
    DATABASE_URL=sqlite:////app/database/users_courses.db \
    CONTENT_ROOT_DIR=/app/categories-data \
    BACKUP_DIR=/app/backups \
    KRB5_CONFIG=/etc/krb5.conf

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=45s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=5).read()"

CMD ["python", "-u", "run.py"]
