# Запуск на удалённом / корпоративном Windows-ПК

Полный шаблон переменных окружения: файл **`env.corporate-remote.example`** в корне репозитория. Скопируйте его в **`.env`** и подставьте свои значения (realm, DC, секреты).

## Автоустановка (рекомендуется): `setup-windows.bat`

Из корня репозитория (или скопируйте `setup-windows.bat` и папку `scripts` вместе с проектом):

```powershell
.\setup-windows.bat
```

- Если это уже git-репозиторий: `git pull`, `.venv`, `pip install`, при необходимости создание `.env` и подстановка `SECRET_KEY`.
- Если указать **несуществующий** каталог первым аргументом — выполнится `git clone` с веткой (второй аргумент, по умолчанию `main`).

Примеры:

```cmd
setup-windows.bat
setup-windows.bat D:\Apps\nauth_test develop
```

Переменные перед запуском из `cmd`:

```cmd
set NAUTH_REPO=https://github.com/IVANIArgb/nauth_test.git
set NAUTH_BRANCH=main
set NAUTH_USE_DOCKER=1
setup-windows.bat
```

Логика в `scripts\setup-project.ps1`. После установки можно запускать **`run-server.bat`** (создаётся скриптом) или `python run.py`.

### Если «всё сделал, но ошибки те же»

Частая причина: файл **`.content_root_dir_override`** в корне проекта (важнее пустого `CONTENT_ROOT_DIR` в `.env`) — там остаётся `C:\Users\Пользователь\...`.

```powershell
cd C:\Users\ManakovIV\nauth_test
.\scripts\fix-corporate-install.ps1
```

Затем **закройте** старое окно с `python run.py`, снова `.\run-server.bat`, в браузере **Ctrl+Shift+R**.

## Быстрый старт вручную (PowerShell)

Из корня репозитория (папка с `run.py`):

```powershell
# 1) Виртуальное окружение (один раз)
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

# 2) Конфиг (один раз): скопировать шаблон → .env и отредактировать блоки YOUR_*
Copy-Item -Path .\env.corporate-remote.example -Destination .\.env

# 3) Запуск
python .\run.py
```

Либо скрипт (копирует шаблон в `.env`, только если `.env` ещё нет):

```powershell
.\scripts\start-corporate-remote.ps1
```

После старта в логе найдите строку **`learningsite.startup`** — там фактический путь контента и флаги `TEST_MODE`, `TRUST_REMOTE_USER`, `KERBEROS_GSSAPI_ENABLED`. Сравнивайте её с домашним ПК при расхождениях.

## Режимы `FLASK_ENV`

| Значение | Когда использовать |
|----------|---------------------|
| `development` | Внутренняя сеть, HTTP, отладка, пока нет HTTPS-терминатора. Проще с cookies. |
| `production` | За reverse-proxy с HTTPS. Включены жёсткие проверки: нельзя `TEST_MODE`, `DOCKER_AUTH_FALLBACK`, небезопасный `SECRET_KEY`; при `TRUST_REMOTE_USER=true` нужен `TRUST_REMOTE_USER_CONFIRM=true`; при включённом терминале в prod — `ALLOW_TERMINAL_IN_PROD=true`. |

## Два типичных сценария аутентификации

### A) Прямой доступ к Flask (порт 5000 и т.д.)

- В `.env`: `TRUST_REMOTE_USER=false`, `KERBEROS_GSSAPI_ENABLED=false` (если нет keytab в приложении).
- Логин: **учётная запись Windows**, под которой запущен браузер, через `WindowsIdentity` / fallback (см. `auth/auth_script.py`).
- Kerberos в браузере на `http://127.0.0.1` часто **не** передаётся как на FQDN в intranet — для полноценного SSO обычно нужен **вариант B** или FQDN в зоне intranet.

### B) За IIS / nginx с Integrated Windows Auth или другим SSO

- Прокси проверяет пользователя и передаёт логин заголовком (`X-Remote-User`, `Remote-User` и т.д.).
- В `.env`: `TRUST_REMOTE_USER=true`, для `FLASK_ENV=production` обязательно **`TRUST_REMOTE_USER_CONFIRM=true`**.
- Кириллица в логине: заголовок **`X-Remote-User-B64`** (UTF-8 → base64), см. `auth/new_auth.py`.

## Порты и сеть

- `HOST=127.0.0.1` — сайт только локально.
- `HOST=0.0.0.0` — слушать все интерфейсы (доступ по IP из LAN). Согласуйте с ИБ; часто вместо этого используют IIS как reverse-proxy на 443.

На Windows **`run.py` всегда использует встроенный сервер Flask** (gunicorn в `run.py` отключается). Для промышленного Windows-сервера часто выбирают **waitress** или **IIS + HttpPlatformHandler** / обратный прокси на Linux с gunicorn — это уже вне текущего `run.py`.

## Контент `CONTENT_ROOT_DIR`

- Пустое значение → каталог **`categories-data`** в корне проекта.
- Свой путь → только каталог, доступный **пользователю, от которого запущен Python** (не чужой `C:\Users\...` с другого ПК).
- При ошибке доступа приложение откатывается на встроенный `categories-data` и пишет предупреждение в лог.

## Полезные файлы

- Общий шаблон: `env.example`
- Корпоративный шаблон: `env.corporate-remote.example`
- Различия дом / работа: `docs/mds/corporate-vs-local-deployment.md`
- Docker (другой сценарий): `docker-compose.yml`, `docker-compose.sso.yml`
