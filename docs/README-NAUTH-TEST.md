# nauth_test — SSO без keytab (установка на удалённый ПК)

Репозиторий: **https://github.com/IVANIArgb/nauth_test**

Kerberos проверяется на **reverse-proxy** (nginx); Flask принимает логин из `X-Remote-User` / `X-Remote-User-B64` (кириллица).

## Установка (Windows PowerShell)

**Не используйте** `powershell -Command "$env:NAUTH_SSO_USER=..."` — внешняя оболочка ломает `$env` и кириллицу.

```powershell
$env:NAUTH_SSO_USER = 'ManakovIV'
irm https://raw.githubusercontent.com/IVANIArgb/nauth_test/main/scripts/install-nauth_test.ps1 | iex
```

Кириллица в логине — те же две строки в **этом же** окне PowerShell:

```powershell
$env:NAUTH_SSO_USER = 'Пользователь'
irm https://raw.githubusercontent.com/IVANIArgb/nauth_test/main/scripts/install-nauth_test.ps1 | iex
```

Требуется **Docker Desktop** (проверка: `docker version`).

## Установка через git

```powershell
git clone https://github.com/IVANIArgb/nauth_test.git $env:USERPROFILE\nauth_test
cd $env:USERPROFILE\nauth_test
.\scripts\install-nauth_test.ps1
```

## Linux

```bash
curl -fsSL https://raw.githubusercontent.com/IVANIArgb/nauth_test/main/scripts/install-nauth_test.sh | bash
```

## После установки

| URL | Назначение |
|-----|------------|
| http://localhost:8080/ | Сайт через SSO-прокси |
| http://localhost:8080/user/info-test | Логин и `auth_method` |
| http://localhost:8000/ | Прямой доступ (без SSO → guest) |

Остановка:

```powershell
cd $env:USERPROFILE\nauth_test
docker compose -f docker/docker-compose.yml -f docker/docker-compose.sso.yml down
```

## Требования

- Docker Desktop (Windows) или Docker Engine (Linux)
- Git
- Порты **8080** и **8000** свободны

## Переменные (.env)

Скопируйте `docker/docker.env.sso.example` → `.env`:

- `SSO_DEFAULT_USER` — логин после SSO (латиница или кириллица)
- `WEB_PORT` — внешний порт прокси (по умолчанию 8080)
