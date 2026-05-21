# Инвентаризация «мусора» в репозитории (ничего не удалено)

Снимок: ветка `nauth`, локальная машина разработки.  
Цель: что можно убрать, архивировать или не копировать на другой ПК.

---

## 1. Критично по размеру (локально, в `.gitignore`)

| Путь | ~Размер | Зачем было | Рекомендация |
|------|---------|------------|--------------|
| `docker_export/learnsite-web-image.tar` | ~1.3 GB | Экспорт Docker-образа | Не хранить в проекте; пересобрать `docker compose build` |
| `docker_export/learnsite-web-light.tar` | ~76 MB | Облегчённый образ | То же |
| `docker_export/learnsite-web-light.zip` | ~76 MB | Архив образа | То же |
| `LNSVImage/` | ~153 MB | Медиа/картинки | Вынести на диск/CDN или отдельное хранилище |
| `.venv/` | сотни MB | Python venv | Не переносить; `pip install -r requirements.txt` |
| `backend/logs/app.log` | ~2 MB | Логи рантайма | Ротация / удаление локально |

---

## 2. Локальный мусор (не в git, появляется при работе)

| Файл/папка | Примечание |
|------------|------------|
| `debug-2fa264.log` | Отладочная сессия агента; не коммитить |
| `test-out.txt` | Временный вывод теста shell |
| `.content_root_dir_override` | Runtime; часто ломает пути при переносе ПК |
| `.env` | Секреты и машинные пути; не копировать между ПК |
| `.pytest_cache/` | Кэш pytest |
| `.idea/` | JetBrains IDE |
| `tests/reports/junit.xml` | Отчёт CI/локальных тестов |
| `database/*.db` | SQLite с пользователями |
| `kerberos/keytabs/*` | Keytab (секрет), в gitignore |
| `__pycache__/`, `*.pyc` | Python cache |

---

## 3. Устаревший код (в git, нигде не импортируется)

| Файл | Статус |
|------|--------|
| `backend/simplified_real_kerberos_auth.py` | Заменён на `auth/new_auth.py` + `auth/auth_script.py` |
| `backend/real_kerberos_auth.py` | Старый Kerberos; не подключается в `backend/__init__.py` |

Удаление возможно после явной проверки, что нет внешних скриптов.

---

## 4. Папка `scripts/legacy/` (20 файлов в git)

Старые restore/setup/test/maintenance скрипты. Дублируют:

- `scripts/setup-project.ps1`, `setup-windows.bat`
- `scripts/fix-corporate-install.ps1`
- `run.py`, `start/setup_env.py`

| Подпапка | Содержимое |
|----------|------------|
| `legacy/restore/` | Откаты git-версий (`restore_to_f426438.py`, …) |
| `legacy/setup/` | Старый krb5, `run_dev.sh` |
| `legacy/tests/` | Ручные тесты, не pytest |
| `legacy/maintenance/` | Очистка БД, `pack_for_transfer.py` (дубль `pack-for-transfer.ps1`) |

Рекомендация: архив в `docs/archive/` или отдельная ветка, не тащить на prod-ПК.

---

## 5. Дубли установки / публикации (в git, пересекаются)

| Файл | Назначение |
|------|------------|
| `REMOTE-INSTALL.ps1` | Обёртка → `install-nauth_test.ps1` |
| `scripts/install-nauth_test.ps1` | Docker SSO install |
| `scripts/install-nauth_test.sh` | То же для Linux |
| `scripts/setup-project.ps1` | Native Windows + git clone |
| `setup-windows.bat` | Вызов setup-project |
| `scripts/publish-nauth_test-github.ps1` | Публикация на GitHub |
| `PUSH-TO-GITHUB.ps1` | Ручной push (одноразовый) |
| `scripts/pack-for-transfer.ps1` | ZIP для переноса |
| `start/setup_env.py` / `start/setup_env.sh` | Ещё один генератор `.env` |

Можно оставить: `setup-windows.bat` + `install-nauth_test.ps1` + `env.example`; остальное — «обёртки для удобства».

---

## 6. Дубли конфигов Kerberos / env

| Группа | Файлы |
|--------|-------|
| Kerberos в корне | `kerberos/krb5.conf`, `kerberos/krb5.conf.example`, `kerberos/conf/krb5.conf`, `kerberos/conf/kdc.conf` |
| Env-шаблоны | `env.example`, `env.corporate-remote.example`, `env.development.example`, `docker.env.example`, `docker.env.sso.example`, `kerberos/env.kerberos.example` |

Не мусор, но при переносе ПК путать легко — держать один рабочий `.env` из шаблона.

---

## 7. `kerberos_ad_service/` — отдельный микросервис

Полный подпроект (Docker, k8s, тесты). Основное приложение LearningSite использует `auth/` напрямую.

| Что лишнее внутри | Примечание |
|-------------------|------------|
| `k8s/generated/*.yaml` | Дубли `*.template.yaml` после render |
| `k8s/*.yaml` + `*.template.yaml` | Пары generated/ручные |

Нужен только если деплоите **отдельный** Kerberos+AD сервис; иначе — кандидат на вынос в другой репозиторий.

---

## 8. Дубли фронтенда (не удалять без рефакторинга)

| Дубликат | Хеши совпадают? |
|----------|-----------------|
| `frontend/admin-pages/templates/js/custom-modal.js` vs `user-pages/...` | **Нет** (разные версии) |
| `frontend/admin-pages/templates/css/custom-modal.css` vs `user-pages/...` | **Да** (идентичны) |
| `custom-modal.js` на страницах + `base_static_page.html` | Двойная загрузка на части страниц (исправлено IIFE на `nauth`) |

Рефакторинг: один общий `frontend/shared-pages/templates/`.

---

## 9. Временная отладка (убрать после закрытия бага)

| Файл | Назначение |
|------|------------|
| `backend/utils/agent_debug_log.py` | Пишет `debug-2fa264.log` |
| Логи `#region agent log` в `categories_data_sync.py`, `api.py`, `custom-modal.js` | Debug mode |

---

## 10. Не в git, стоит добавить в `.gitignore` (если появляется снова)

- `debug-*.log`
- `test-out.txt`
- `*.tar` / крупные zip в корне (кроме явных релизов)

---

## Что **не** мусор

- `categories-data/` — учебный контент (может быть пустым)
- `auth/`, `backend/api.py`, `docker-compose*.yml` — рабочее ядро
- `tests/` (кроме `reports/`) — автотесты
- `docs/mds/` — документация
