# Kerberos + AD + Flask в Docker

## Архитектура

1. Браузер отправляет `Authorization: Negotiate ...` в `Flask /auth/me`.
2. `KerberosAuthenticator` валидирует SPNEGO и извлекает `user@REALM`.
3. `ADClient` ищет пользователя в AD по `sAMAccountName` через LDAP + GSSAPI.
4. `UserRepository` пишет результат запроса в SQLite/PostgreSQL.
5. API возвращает JSON, а Prometheus читает `/metrics`.

## Внешние зависимости

- KDC/AD контроллер домена.
- LDAP endpoint (обычно AD DC по `ldap://` или `ldaps://`).
- DNS резолвинг SPN и контроллеров домена.
- Keytab для сервисного principal (`HTTP/<fqdn>@REALM`).

## Переменные окружения

- `APP_ENV`, `HOST`, `PORT`, `DEBUG`
- `SPN_HOSTNAME`, `KERBEROS_SERVICE_NAME`, `KERBEROS_REALM`, `KERBEROS_KEYTAB`, `KRB5_CONFIG`
- `LDAP_URI`, `LDAP_BASE_DN`, `LDAP_CONNECT_TIMEOUT_S`, `LDAP_READ_TIMEOUT_S`
- `DATABASE_URL` (`sqlite:///users.db` или `postgresql+psycopg://...`)
- `RATE_LIMIT_DEFAULT`, `RATE_LIMIT_AUTH`, `RATE_LIMIT_STORAGE_URI`
- `LOG_LEVEL`, `PROMETHEUS_ENABLED`, `OTEL_ENABLED`
- `PREFLIGHT_ENABLED`, `PREFLIGHT_KINIT_ENABLED`

## Ошибки и таймауты

- SPNEGO/LDAP ошибки возвращаются как `401` с `WWW-Authenticate: Negotiate`.
- LDAP запросы идут с retry (`tenacity`) и таймаутами на connect/read.
- `/health` возвращает `503`, если недоступны keytab, LDAP или БД.

## Настройка браузеров для Kerberos SSO

- **Chrome/Edge (Windows GPO):**
  - Добавить URL сервиса в `AuthServerAllowlist` (например, `http://app.example.com`).
  - В интранет-зоне включить автоматическую передачу логина.
- **Firefox:**
  - `about:config`:
    - `network.negotiate-auth.trusted-uris=app.example.com`
    - `network.negotiate-auth.delegation-uris=app.example.com` (если нужна delegation).
- Проверить получение SPNEGO:
  - `curl -v --negotiate -u : http://localhost:5000/auth/me`

## Диагностика контейнера

При старте контейнера `entrypoint.sh` автоматически выполняет preflight:

- проверка наличия `krb5.conf` и `keytab`;
- принудительные права на keytab `0400`;
- `kinit -k -t ...` + `klist` (если `PREFLIGHT_KINIT_ENABLED=true`);
- `nslookup` LDAP/KDC хоста.

- `kinit -k -t /run/secrets/service_keytab HTTP/<fqdn>@REALM && klist`
- `ldapsearch -H ldap://dc01.example.com -Y GSSAPI -b "DC=example,DC=com" "(sAMAccountName=test)"`
- `nslookup dc01.example.com`
- `nc -vz dc01.example.com 88`
- `nc -vz dc01.example.com 389`

---

## Основное приложение LearningSite (Flask) без keytab в контейнере

Проверка Kerberos‑билета в приложении требует учётных данных сервиса (keytab или эквивалент). Если keytab **нет**, безопасная схема такая:

1. Пользователь ходит на **reverse-proxy** (например IIS с Windows Authentication / negotiate), который проверяет SPNEGO и **не пропускает** наружу поддельный `Authorization: Negotiate` от клиента.
2. Прокси подставляет проверенный логин в заголовок (`X-Remote-User`, `Remote-User` и т.д.) во **внутреннюю** сеть к контейнеру.
3. В контейнере включают **`TRUST_REMOTE_USER=true`**, список заголовков — **`REMOTE_USER_HEADERS`**, в production — **`TRUST_REMOTE_USER_CONFIRM=true`**.

Переменная **`ALLOW_INSECURE_NEGOTIATE_HEURISTIC`** (по умолчанию выключена): «разбор» `Negotiate` без GSSAPI **не** является проверкой Kerberos; в **Docker** она принудительно отключена даже при `true`.

Логины в AD могут быть на кириллице: доверенный заголовок нормализуется с поддержкой Unicode (`auth/new_auth.py`).
