# LSiteSV (LearningSiteSV) — система уроков и тестов

**GitHub:** https://github.com/IVANIArgb/LSiteSV

Учебный портал с курсами, уроками и встроенными тестами. Сейчас **весь учебный контент хранится в файловой системе**, а база данных используется только для пользователей, ролей и прогресса.

## Установка

**Ubuntu (без Docker):** [`docs/mds/deploy.md`](docs/mds/deploy.md)

**Windows:** `git pull` + `update.bat` (из корня репозитория)

Профиль из **Active Directory без keytab**: `docker/docker.env.sso-ad.example` → `.env`, см. [`docs/mds/docker-sso-ldap-no-keytab.md`](docs/mds/docker-sso-ldap-no-keytab.md). Docker: [`docker/README.md`](docker/README.md).

## Фронтенд-структура

Страницы и шаблоны фронтенда находятся в папке `frontend`:

- `frontend/admin-pages` — страницы и шаблоны админской части;
- `frontend/user-pages` — страницы и шаблоны пользовательской части;
- `frontend/shared-pages` — общие страницы/partials для обеих ролей.

## Где лежит контент

По умолчанию контент находится в папке `categories-data` в корне проекта, либо в каталоге, указанном в переменной окружения `CONTENT_ROOT_DIR`.

Структура:

- `category-*/config.json` — настройки категории (id, title, порядок, флаг последовательного прохождения и т.п.).
- `category-*/course-*/config.json` — настройки курса (id, title, описание, порядок, sequential_progression, total_lessons, is_active).
- `category-*/course-*/lesson-*/config.json` — настройки урока (id, title, lesson_number, is_active и др.).
- `category-*/course-*/lesson-*/texts/block-<id>.txt` — текстовые блоки и заголовки урока.
- `category-*/course-*/lesson-*/images/` — изображения, к которым ссылаются блоки `image`.
- `category-*/course-*/lesson-*/videos/` — видео‑файлы (если используются локальные видео).
- `category-*/course-*/lesson-*/files/` — прикреплённые файлы.
- `category-*/course-*/lesson-*/tests/` — файлы тестов для урока.

### Папка `tests/` внутри урока

Для каждого урока с тестированием создаётся:

- `tests/block-<id>/config.json` — настройки конкретного тест‑блока (заголовок, порог, попытки, тип).
- `tests/block-<id>/questions/q001.txt`, `q002.txt`, … — по одному файлу на вопрос.

Минимальный набор полей `config.json`:

- `title` — название теста.
- `enabled` — включён/выключен тест.
- `pass_percent` — порог прохождения в процентах (по умолчанию 70).
- `limit_attempts` — флаг ограничения числа попыток.
- `max_attempts` — сколько попыток доступно (если `limit_attempts = true`).  
- `test_type` — `\"permanent\"` (постоянный) или `\"temporary\"` (временный).
- `available_from` / `available_until` — ISO‑даты для временных тестов.
- `shuffle_questions`, `shuffle_options` — перемешивание вопросов и вариантов.

Рекомендуемый формат `qXXX.txt`:

```text
Q: Текст вопроса
A) Вариант A
B) Вариант B
POINTS: 1
TYPE: single        # или multiple, или input
CORRECT: A          # для multiple: CORRECT: A,C
ACCEPTED: да, верно # только для TYPE: input
```

Фронтенд разбирает эти файлы и отдаёт их в виде привычной структуры `questions[]`.

## Что хранится в БД

База данных остаётся источником правды только для:

- пользователей и ролей;
- прогресса по курсам и урокам (`UserCourseProgress`, `UserLessonProgress`);
- результатов попыток прохождения тестов (`lesson_test_results`);
- служебных сущностей (вопросы на форуме и т.п.).

Контент категорий/курсов/уроков **не читается из БД** — только из файлов.

## Основные эндпоинты API

- `GET /api/categories`, `GET /api/categories/<id>` — читают категории из `categories-data`.
- `GET /api/courses`, `GET /api/courses/<id>` — читают курсы из файлов (с уроками).
- `GET /api/lessons`, `GET /api/lessons/<id>` — читают уроки и статус прохождения.
- `GET /api/lessons/<id>/blocks` — собирает блоки урока из `blocks.json` + `texts/`, `images/`, `videos/`, `files/`, `tests/`.
- `POST/PUT/DELETE /api/lessons/<id>/blocks` — редактирование блоков через файловую систему (используется админкой).
- `POST /api/lessons/<lesson_id>/blocks/<block_id>/submit-test` — проверка теста; вопросы и настройки читаются из `tests/`, результат пишется в `lesson_test_results`.
- `GET /api/lessons/<lesson_id>/tests/status` — статус тестов по уроку (пройдено/попытки/лимиты) для текущего пользователя.
- `POST /api/lessons/<lesson_id>/complete` — завершение урока; не даёт завершить, если есть непройденный тест.

## Миграция контента из БД в FS

Для переноса существующих данных в файловую структуру есть скрипт:

```bash
python scripts/sync_content_fs_from_db.py
```

Он:

- создаёт/обновляет папки категорий, курсов и уроков;
- заполняет `config.json` для каждой сущности;
- экспортирует текстовые блоки в `texts/block-<id>.txt`;
- экспортирует тесты в `tests/block-<id>/config.json` и `tests/block-<id>/questions/*.txt`;
- формирует `blocks.json` в каждой папке урока.

## Как работать с тестами

Администраторы редактируют тесты через UI:

- модалка «Редактировать тест» разделена на вкладки **«Настройки» / «Вопросы»**;
- добавление/редактирование вопроса делает запросы к API, которое обновляет файлы в `tests/`;
- при прохождении теста пользователь видит количество попыток, статус и подробный фидбек по каждому вопросу.

Файлы в `tests/` можно при необходимости править вручную (особенно удобно в внешнем `CONTENT_ROOT_DIR`), но рекомендуется использовать админ‑панель, чтобы не нарушить формат. +
