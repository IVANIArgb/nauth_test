# Хостинг: Docker без keytab, мультиюзер AD

## Схема

1. Пользователь в браузере (доменный Windows).
2. **Корпоративный прокси** (IIS + Windows Authentication или шлюз Kerberos) проверяет личность и передаёт `X-Remote-User: login`.
3. Контейнер **nginx** пробрасывает заголовок во Flask.
4. Flask по логину ходит в **AD по LDAP** (ФИО, отдел) и при первом визите создаёт запись в SQLite.

Keytab в Linux-контейнере **не нужен**. Пользователей заранее не вносят.

## У себя (сборка образа)

```powershell
.\scripts\package-hosting-image.ps1
```

Файл: `dist\learnsite-web.tar`

## На хостинге

```bash
docker load -i learnsite-web.tar
cp docker/docker.env.hosting.example .env
# отредактировать LDAP_*, SECRET_KEY, TRUSTED_PROXY_IPS
docker compose -f docker/docker-compose.yml -f docker/docker-compose.hosting.yml up -d
```

Сайт: `http://<server>:8080/`

## Обязательно в `.env`

| Переменная | Назначение |
|------------|------------|
| `LDAP_SERVER`, `LDAP_BASE_DN` | AD из контейнера |
| `LDAP_USER`, `LDAP_PASSWORD` | служебная учётка только на чтение |
| `TRUST_REMOTE_USER=true` | доверять логину с прокси |
| `TRUSTED_PROXY_IPS` | CIDR корпоративного прокси |

## IIS перед Docker (Windows Server)

См. `deploy/iis/arr-windows-auth-web.config` — Windows Auth → `X-Remote-User` → `http://127.0.0.1:8080/`.

## Сеть

Из контейнера `web` до контроллера домена: **TCP 389** (или **636** при `LDAP_USE_SSL=true`).
