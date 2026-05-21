# Глубокий аудит: баги, уязвимости, недоделки

Дата: 2026-05-20, ветка `nauth`.  
Исходный отчёт; ниже — статус исправлений (кроме **C1/C2** — тестовые фичи, убираются в prod вручную).

## Статус исправлений (2026-05-20)

| ID | Статус |
|----|--------|
| C1, C2 | Не трогали (по запросу) |
| C3 | Исправлено: `auth/trusted_proxy.py`, проверка IP в `auth/new_auth.py` |
| C4 | Исправлено: `sanitize_ad_login`, `Get-ADUser -Filter` |
| C5 | Исправлено: fail-fast учебного `SECRET_KEY` без `INSECURE_DEV_SECRET=true` |
| H1 | Исправлено: `_require_admin` на `/api/statistics` |
| H2 | Исправлено: auto-DEBUG только localhost; `/debug/auth` блок при `TRUST_REMOTE_USER` |
| H3 | Исправлено: дефолт `MAX_CONTENT_LENGTH` 100 MB |
| H4 | Документировано + `RATELIMIT_STORAGE_URI` |
| H5 | Исправлено в `ProductionConfig`: CSP enforcing, `script-src 'self'` |
| H6 | Комментарий + `SESSION_COOKIE_SAMESITE=Strict` в production |
| H7 | Эксплуатация: см. `env.example` / firewall (код compose не меняли) |
| M1 | Исправлено: `_forbidden_content_root_path` |
| M2 | Уже было: `TEST_MODE` запрещён при `FLASK_ENV=production` |
| M4 | Исправлено: magic bytes в `file_upload.py` |
| M5 | Архив: `backend/legacy/` |
| M6 | Исправлено: `agent_debug_log` только при `AGENT_DEBUG_LOG=true` |
| M7 | Исправлено: `show-settings` только `super_admin` |
| L3 | Исправлено: убраны кнопки edit/move блоков |
| L6 | Исправлено: SQLite WAL в `database/models.py` |
| L7 | Уже было: `RotatingFileHandler` в `logging_config.py` |

---

## Критично (безопасность / эскалация прав)

| # | Область | Проблема | Где |
|---|---------|----------|-----|
| C1 | Терминал | При `TERMINAL_ROLE_COMMANDS_ENABLED=true` **любой** аутентифицированный пользователь может выполнить `change-role-admin` / `change-role-super-admin` и повысить себе роль в БД. | `backend/api.py` → `terminal_role_command` |
| C2 | Docker по умолчанию | В `docker-compose.yml` **`TERMINAL_ROLE_COMMANDS_ENABLED` default `true`**, `DOCKER_AUTH_FALLBACK=true`, учебный `SECRET_KEY`. | `docker-compose.yml`, `docker.env.example` |
| C3 | TRUST_REMOTE_USER | Если прокси **не перезаписывает** заголовки `X-Remote-User` / `Remote-User`, клиент может подставить чужой логин → полный доступ под этой учёткой. | `auth/new_auth.py`, `docker.env.sso.example` |
| C4 | PowerShell / AD | `Get-ADUser -Identity "{login}"` — логин вставляется в команду. Сейчас логин фильтруется в `new_auth` (`[\w.-]`), но **прямой вызов** `ADUserInfo` с непроверенным логином = риск injection. | `auth/ad_user_info.py:54-60` |
| C5 | Секреты в образе | `SECRET_KEY=learnsite-docker-dev-key-not-for-production` в compose — при `FLASK_ENV=production` есть fail-fast, при **`development` в prod** — нет. | `docker-compose.yml` |

---

## Высокий риск

| # | Область | Проблема | Где |
|---|---------|----------|-----|
| H1 | API | `GET /api/statistics` — **нет** `_require_admin`, любой аутентифицированный пользователь видит число пользователей, отделы, курсы. | `backend/api.py` `get_statistics` |
| H2 | Конфиг | `run.py`: при `FLASK_ENV=development` автоматически `DEBUG=true` → `/debug/auth` отдаёт заголовки и данные пользователя. | `run.py`, `backend/routes.py` `debug_auth` |
| H3 | Загрузки | `MAX_CONTENT_LENGTH` по умолчанию **1 GB** — риск исчерпания диска/памяти при множественных upload. | `backend/config.py` |
| H4 | Rate limit | `Limiter(..., storage_uri="memory://")` — лимиты **на процесс**, не кластер; при рестарте сброс; обход с множества IP. | `backend/__init__.py` |
| H5 | CSP | `script-src 'self' 'unsafe-inline'` — слабая защита от XSS при появлении инъекции в HTML. | `backend/config.py` `CSP_POLICY` |
| H6 | CSRF | Весь `api_bp` **exempt** от CSRF. Если когда‑либо появится cookie‑сессия без SameSite=Strict, возможны cross-site POST. | `backend/__init__.py` |
| H7 | Хост | `HOST=0.0.0.0` в Docker — слушает все интерфейсы; без firewall доступен из LAN. | `docker-compose.yml` |

---

## Средний риск / логические баги

| # | Область | Проблема | Где |
|---|---------|----------|-----|
| M1 | Контент | `.content_root_dir_override` и `CONTENT_ROOT_DIR` в `.env` — при переносе ПК ломают доступ (`WinError 5`); частично лечится на `nauth`, но легко снова записать через UI. | `categories_data_sync.py`, admin UI |
| M2 | TEST_MODE | В `TEST_MODE` все считаются **admin** в `_effective_role` — случайное включение в prod даёт полный доступ (есть блок только для `FLASK_ENV=production`). | `backend/api.py`, `backend/routes.py` |
| M3 | Guest vs API | UI может работать как guest, API режет guest — хорошо; но терминал при включённом флаге пускает без Kerberos. | `api.py` `_is_authenticated_user` |
| M4 | MIME | `validate_mime_type` доверяет `file.mimetype` от клиента — обход расширений возможен. | `backend/utils/file_upload.py` |
| M5 | Дубли auth | Мёртвый код `real_kerberos_auth.py`, `simplified_real_kerberos_auth.py` — риск случайного подключения при рефакторинге. | `backend/` |
| M6 | Отладка в prod | `agent_debug_log` + `#region agent log` пишут пути и ошибки в `debug-*.log` в корне проекта. | `backend/utils/agent_debug_log.py` |
| M7 | `show-settings` | Терминальная команда отдаёт `content_path_resolved`, флаги auth, маскированный `DATABASE_URL` — утечка конфигурации любому, кто может открыть терминал. | `api.py` `_terminal_safe_settings` |

---

## Низкий риск / качество

| # | Область | Проблема | Где |
|---|---------|----------|-----|
| L1 | XSS | Много `innerHTML` без `escapeHtml` в `categories-list.js`, части editor — API‑ошибки иногда вставляются в DOM. | `frontend/**` |
| L2 | Дубли JS | Два почти одинаковых `custom-modal.js` (admin/user); двойная загрузка на страницах. | `frontend/*/templates` |
| L3 | Недоделки UI | `// TODO: Реализовать редактирование блока` и порядок блоков — **не реализовано** (3 копии lesson-editor). | `lesson-editor.js` |
| L4 | Legacy | `scripts/legacy/*` — restore git, старые тесты; путаница при эксплуатации. | `scripts/legacy/` |
| L5 | Kerberos microservice | `kerberos_ad_service/` не связан с основным Flask-приложением; дубли k8s yaml. | отдельная папка |
| L6 | SQLite | Один файл БД без WAL tuning — блокировки при нагрузке multi-worker gunicorn. | `database/` |
| L7 | Логи | `backend/logs/app.log` без ротации в коде. | `logging_config.py` |
| L8 | Исключения | Много `except Exception: pass` в auth/sync — глотание ошибок, сложная диагностика. | `auth/`, `categories_data_sync.py` |

---

## Конфигурация и эксплуатация (частые «баги на удалёнке»)

1. Скопированный `.env` с чужим `CONTENT_ROOT_DIR`.
2. Файл `.content_root_dir_override` после смены папки в UI.
3. Запуск не из ветки `nauth` / старый процесс Python на порту 5000.
4. Docker без `docker-compose.windows.yml` при выборе `C:\...` пути.
5. `FLASK_ENV=development` + `DEBUG=true` на боевом хосте.
6. Кэш статики (до фикса на `nauth`: `SEND_FILE_MAX_AGE_DEFAULT=0` только в `DevelopmentConfig`).

---

## Что сделано хорошо (для баланса)

- API по умолчанию требует аутентификацию (`_require_auth_for_api`).
- Path traversal в `categories-data` и backups — проверки `commonpath`.
- Production fail-fast: `TEST_MODE`, `DOCKER_AUTH_FALLBACK`, `ROOT_TEST`, слабый `SECRET_KEY`, `TRUST_REMOTE_USER` без confirm.
- `FORBIDDEN_EXTENSIONS` для upload.
- `Negotiate` без GSSAPI по умолчанию не доверяется.
- Разделение admin API (`_require_admin` / `_require_super_admin`) на большинстве чувствительных эндпоинтов.

---

## Рекомендуемый порядок исправлений (когда будете фиксить)

1. C1 + C2: терминал только для super_admin; в compose `TERMINAL_ROLE_COMMANDS_ENABLED=false` по умолчанию.
2. H1: `_require_admin` на `/api/statistics`.
3. C3: документация + обязательный strip заголовков на nginx/IIS.
4. C4: параметризованный вызов AD (escape login / LDAP-only).
5. L3: TODO в lesson-editor или скрыть кнопки.
6. Удалить/архивировать мёртвый auth-код после проверки.

---

## Зависимости

Автоматический `pip audit` / `npm audit` в этом прогоне не запускался. Рекомендуется вручную:

```bash
pip install pip-audit
pip-audit -r requirements.txt
```
