# Docker: SSO + LDAP (без keytab) — рекомендуемый режим

## Схема

1. **nginx (sso-proxy)** подставляет `X-Remote-User` = ваш логин AD (`SSO_DEFAULT_USER` в `.env`).
2. **Flask** доверяет только прокси (`TRUST_REMOTE_USER` + `TRUSTED_PROXY_IPS`).
3. **LDAP** в контейнере читает ФИО, отдел, должность из Active Directory.

Keytab и `KERBEROS_GSSAPI_ENABLED` **не нужны**.

## Быстрый старт

```cmd
copy docker.env.sso-ad.example .env
```

Отредактируйте в `.env`:

- `SSO_DEFAULT_USER` — ваш логин AD (sAMAccountName)
- `LDAP_SERVER`, `LDAP_BASE_DN`, `LDAP_USER`, `LDAP_PASSWORD`

```cmd
run-server.bat
```

Сайт: http://localhost:8080/

## Обновление с GitHub

```cmd
update.bat
```

## Если профиль всё ещё GUEST / testadmin

1. Проверьте `LDAP_ENABLED=true` и доступ контейнера к DC (порт 389/636).
2. В `.env` не оставляйте `SSO_DEFAULT_USER=testadmin`.
3. Сброс демо-БД: `docker compose -f docker-compose.yml -f docker-compose.sso.yml down -v` (удалит данные).
