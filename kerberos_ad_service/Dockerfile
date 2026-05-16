FROM python:3.12-slim AS builder

ENV PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /build
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libkrb5-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN python -m venv /opt/venv && /opt/venv/bin/pip install --upgrade pip setuptools wheel \
    && /opt/venv/bin/pip install -r requirements.txt

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    APP_ENV=prod \
    HOST=0.0.0.0 \
    PORT=5000 \
    DEBUG=false \
    KRB5_CONFIG=/etc/krb5.conf

WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends \
    krb5-user \
    libkrb5-3 \
    libgssapi-krb5-2 \
    dnsutils \
    netcat-openbsd \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /opt/venv /opt/venv
COPY app.py config.py requirements.txt entrypoint.sh /app/
COPY krb5.conf /etc/krb5.conf

RUN groupadd -r app && useradd -r -g app app && \
    touch /app/users.db && chown -R app:app /app && chmod 600 /app/users.db && \
    chmod +x /app/entrypoint.sh

USER app
EXPOSE 5000

HEALTHCHECK --interval=30s --timeout=5s --retries=3 --start-period=20s \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:5000/health', timeout=3).read()"

ENTRYPOINT ["/app/entrypoint.sh"]
