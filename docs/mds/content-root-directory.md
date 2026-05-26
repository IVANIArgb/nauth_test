# Выбор папки контента (ПК и Docker)

Учебные файлы (категории, курсы, уроки) лежат в **корне контента** — переменная `CONTENT_ROOT_DIR` или встроенная папка `categories-data` в репозитории.

## Кто может менять путь

Только **`super_admin`**. В главном меню админки: **«Сменить папку контента»** (или API `PUT /api/admin/content-root` с JSON `{"path": "..."}`).

После смены путь пишется в `.env` и в `.content_root_dir_override` (для всех воркеров). **Перезапустите** сервер/контейнер, если что-то не подхватилось.

---

## Вариант A: приложение на Windows (без Docker)

1. Запуск из репозитория: `python run.py` или `run-server.bat`.
2. Войти под пользователем с ролью **super_admin** в БД.
3. Меню → **Сменить папку контента**.
4. Ввести **полный путь**, доступный **тому пользователю Windows**, под которым запущен Python, например:
   - `D:\LearningSiteData`
   - `C:\Users\ManakovIV\Desktop\learning-content`
5. **Нельзя** указывать профиль другого пользователя (`C:\Users\Пользователь\...`) — будет `WinError 5`.
6. Пустой `CONTENT_ROOT_DIR` в `.env` = контент в `<репозиторий>\categories-data`.

---

## Вариант B: Docker на Windows (папка с диска C: или D:)

Контейнер **не видит** `C:\...` напрямую. Нужен compose с монтированием дисков:

```powershell
cd C:\Users\ManakovIV\nauth_test
docker compose -f docker/docker-compose.yml -f docker/docker/docker-compose.windows.yml up -d --build
```

В `docker/docker/docker-compose.windows.yml` диски монтируются как:

| На ПК | В контейнере |
|--------|----------------|
| `C:\` | `/host/C` |
| `D:\` | `/host/D` |

### Как указать путь в UI

В **«Сменить папку контента»** вводите **Windows-путь**, как на ПК:

```
C:\Users\ManakovIV\Desktop\learning-content
```

Приложение в контейнере само переведёт его в:

```
/host/C/Users/ManakovIV/Desktop/learning-content
```

(см. `backend/api.py`, `admin_content_root`).

### В `.env` для Docker (вручную)

```env
CONTENT_ROOT_DIR=/host/C/Users/ManakovIV/Desktop/learning-content
```

Путь **должен** начинаться с `/host/C` или `/host/D` — только если эти тома подключены через `docker/docker-compose.windows.yml`.

---

## Вариант C: Docker без монтирования дисков (только том Docker)

По умолчанию в `docker/docker-compose.yml`:

```env
CONTENT_ROOT_DIR=/app/categories-data
```

Контент в именованном томе `learnsite_content`. Выбор «любой папки с ПК» **недоступен**, пока не добавите volume в compose, например:

```yaml
services:
  web:
    volumes:
      - "D:/MyContent:/app/external-content:rw"
```

и в `.env`:

```env
CONTENT_ROOT_DIR=/app/external-content
```

---

## Переменные для нестандартного монтирования (Linux / свой путь)

Если в `.env` указан Windows-путь, а контейнер Linux без `docker/docker-compose.windows.yml`, можно задать правило замены:

```env
EXTERNAL_CONTENT_MOUNT_FROM_WINDOWS=C:/Users/ManakovIV/Desktop
EXTERNAL_CONTENT_MOUNT_TO_CONTAINER=/host/Desktop
```

Тогда `C:\Users\ManakovIV\Desktop\learning-content` → `/host/Desktop/learning-content` (папка должна быть смонтирована в compose).

---

## Частые ошибки

| Симптом | Причина |
|---------|---------|
| `WinError 5` … `C:\Users\Пользователь` | Чужой профиль или старый `.content_root_dir_override` |
| Путь в UI не применился | Не перезапустили сервер; нет прав super_admin |
| В Docker «папка не создаётся» | Не смонтирован диск (`docker/docker-compose.windows.yml`) |
| Снова старый путь | Файл `.content_root_dir_override` в корне репозитория |

Сброс для корпоративного ПК: `.\scripts\fix-corporate-install.ps1`, затем снова выбрать папку через меню.

## Проверка текущего пути

```http
GET /api/admin/content-root
```

Ответ: `current_root`, `env_value`, `external`, `legacy_root`.
