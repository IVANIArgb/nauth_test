"""
Утилиты для синхронизации файловой структуры categories-data с базой данных.
"""

import logging
import os
import json
import shutil
from slugify import slugify
from typing import Optional, Dict, Any
from pathlib import Path


# Базовый путь к legacy-папке categories-data внутри проекта
_base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LEGACY_CATEGORIES_DATA_PATH = os.path.join(_base_dir, "categories-data")

logger = logging.getLogger(__name__)

_OVERRIDE_FILE = os.path.join(_base_dir, ".content_root_dir_override")

# Базовый путь к categories-data по умолчанию.
# Нужен как явная точка расширения для тестов (monkeypatch) и для будущих интеграций.
# Если задан CONTENT_ROOT_DIR (или override-файл), он имеет приоритет.
BASE_CATEGORIES_DATA_PATH = LEGACY_CATEGORIES_DATA_PATH

def _get_env_root() -> str | None:
    """CONTENT_ROOT_DIR (с приоритетом файла-override, чтобы работало в multi-worker)."""
    # Файл-override нужен, чтобы изменения применялись сразу для всех gunicorn воркеров.
    try:
        if os.path.exists(_OVERRIDE_FILE):
            with open(_OVERRIDE_FILE, "r", encoding="utf-8") as f:
                v = (f.read() or "").strip()
                if v:
                    return v
    except Exception:
        pass

    env_root = os.environ.get("CONTENT_ROOT_DIR")
    if not env_root:
        return None

    # В контейнере часто из .env попадает Windows-путь `C:\...`.
    # Переопределим на контейнерный путь, если это известный volume-маршрут.
    # Если не можем перевести — безопасно откатываемся на legacy-папку внутри проекта.
    if os.name != "nt":
        import re

        if re.match(r"^[a-zA-Z]:[\\/]", env_root.strip()):
            mount_from_win = (os.environ.get("EXTERNAL_CONTENT_MOUNT_FROM_WINDOWS") or "").strip()
            mount_to_container = (os.environ.get("EXTERNAL_CONTENT_MOUNT_TO_CONTAINER") or "/host/Desktop").strip()

            def _norm_win(p: str) -> str:
                return (p or "").strip().lower().replace("\\", "/").rstrip("/")

            mf = _norm_win(mount_from_win)
            rp = _norm_win(env_root)

            if mf and (rp == mf or rp.startswith(mf + "/")):
                suffix = rp[len(mf):].lstrip("/")
                if not suffix:
                    return mount_to_container
                parts = [x for x in suffix.split("/") if x]
                return os.path.join(mount_to_container, *parts)

            return LEGACY_CATEGORIES_DATA_PATH

    return env_root


def _categories_base_is_usable(path: str) -> bool:
    """Проверка, что каталог можно создать/открыть и прочитать (нет WinError 5 и т.п.)."""
    try:
        p = Path(path)
        p.mkdir(parents=True, exist_ok=True)
        next(p.iterdir(), None)
        return True
    except OSError:
        return False


def get_base_categories_data_path() -> str:
    """Вернуть абсолютный путь к корневой папке categories-data."""
    # Явный override (в первую очередь для тестов через monkeypatch).
    # Должен иметь приоритет над переменными окружения, чтобы тесты были изолированы
    # и не зависели от локальной конфигурации разработчика.
    if BASE_CATEGORIES_DATA_PATH and BASE_CATEGORIES_DATA_PATH != LEGACY_CATEGORIES_DATA_PATH:
        candidate = os.path.abspath(os.path.expanduser(BASE_CATEGORIES_DATA_PATH))
    else:
        env_root = _get_env_root()
        if env_root:
            candidate = os.path.abspath(os.path.expanduser(env_root))
        else:
            candidate = os.path.abspath(os.path.expanduser(BASE_CATEGORIES_DATA_PATH))

    legacy_abs = os.path.abspath(os.path.expanduser(LEGACY_CATEGORIES_DATA_PATH))

    if _categories_base_is_usable(candidate):
        return candidate

    if candidate != legacy_abs:
        logger.warning(
            "Корень контента недоступен для текущего пользователя (%r). "
            "Проверьте CONTENT_ROOT_DIR и права. Используется встроенная папка categories-data.",
            candidate,
        )
    if not _categories_base_is_usable(legacy_abs):
        raise PermissionError(
            f"Нет доступа ни к CONTENT_ROOT_DIR ({candidate!r}), ни к {legacy_abs!r}"
        )
    # #region agent log
    try:
        from backend.utils.agent_debug_log import agent_debug_log

        agent_debug_log(
            "H5",
            "categories_data_sync.get_base_categories_data_path",
            "fallback to legacy",
            {"candidate": candidate, "legacy_abs": legacy_abs},
        )
    except Exception:
        pass
    # #endregion
    return legacy_abs


def is_external_content_root() -> bool:
    """
    True, если фактически используется каталог вне встроенного categories-data проекта.

    Учитывает откат get_base_categories_data_path() при недоступном CONTENT_ROOT_DIR
    (иначе на корпоративном ПК с «чужим» путём из .env логика дубликатов/синка вела себя как для внешнего диска).
    """
    if not _get_env_root():
        return False
    try:
        effective = os.path.normcase(os.path.abspath(get_base_categories_data_path()))
    except OSError:
        return False
    legacy_abs = os.path.normcase(os.path.abspath(os.path.expanduser(LEGACY_CATEGORIES_DATA_PATH)))
    return effective != legacy_abs


def _clear_unusable_content_root_override() -> bool:
    """
    Удалить .content_root_dir_override, если путь недоступен текущему процессу.
    Этот файл важнее CONTENT_ROOT_DIR в .env — из‑за него часто остаётся C:\\Users\\Пользователь\\...
    """
    try:
        if not os.path.exists(_OVERRIDE_FILE):
            return False
        with open(_OVERRIDE_FILE, "r", encoding="utf-8") as f:
            raw = (f.read() or "").strip()
        if not raw:
            os.remove(_OVERRIDE_FILE)
            return True
        candidate = os.path.abspath(os.path.expanduser(raw))
        legacy_abs = os.path.abspath(os.path.expanduser(LEGACY_CATEGORIES_DATA_PATH))
        if candidate == legacy_abs or _categories_base_is_usable(candidate):
            return False
        os.remove(_OVERRIDE_FILE)
        logger.warning(
            "Удалён недоступный .content_root_dir_override (%r). "
            "Используется categories-data в проекте или CONTENT_ROOT_DIR из .env.",
            raw,
        )
        return True
    except OSError as ex:
        logger.warning("Не удалось проверить/удалить .content_root_dir_override: %s", ex)
        return False


def ensure_content_root_env_matches_process() -> None:
    """
    Убрать из окружения и override-файла недоступные пути контента (копирование .env с другого ПК).

    Вызывать после load_dotenv (create_app).
    """
    legacy_abs = os.path.abspath(os.path.expanduser(LEGACY_CATEGORIES_DATA_PATH))

    _clear_unusable_content_root_override()

    raw = (os.environ.get("CONTENT_ROOT_DIR") or "").strip()
    if raw:
        candidate = os.path.abspath(os.path.expanduser(raw))
        if candidate != legacy_abs and not _categories_base_is_usable(candidate):
            os.environ.pop("CONTENT_ROOT_DIR", None)
            logger.warning(
                "CONTENT_ROOT_DIR из окружения недоступен процессу (%r) — переменная сброшена. "
                "Задайте путь, доступный текущему пользователю Windows, или оставьте пустым для categories-data в проекте.",
                raw,
            )

    # #region agent log
    try:
        from backend.utils.agent_debug_log import agent_debug_log

        ov = None
        if os.path.exists(_OVERRIDE_FILE):
            with open(_OVERRIDE_FILE, "r", encoding="utf-8") as f:
                ov = (f.read() or "").strip()
        agent_debug_log(
            "H1",
            "categories_data_sync.ensure_content_root_env_matches_process",
            "content roots after sanitize",
            {
                "override_file": ov,
                "env_CONTENT_ROOT_DIR": os.environ.get("CONTENT_ROOT_DIR"),
                "resolved_base": get_base_categories_data_path(),
                "cwd": os.getcwd(),
            },
        )
    except Exception as ex:
        from backend.utils.agent_debug_log import agent_debug_log

        agent_debug_log(
            "H1",
            "categories_data_sync.ensure_content_root_env_matches_process",
            "sanitize log failed",
            {"error": str(ex)},
        )
    # #endregion


def _iter_category_dirs():
    """Внутренний генератор: папки категорий в корневом хранилище."""
    ensure_categories_data_directory()
    base = Path(get_base_categories_data_path())
    if not base.exists():
        return
    for entry in base.iterdir():
        if entry.is_dir() and entry.name.startswith("category-"):
            yield entry


def get_existing_category_ids_from_fs() -> set[int]:
    """
    Вернуть множество ID категорий, для которых в текущем CONTENT_ROOT_DIR
    существует папка категории с config.json.
    Используется, чтобы при смене внешнего хранилища не показывать старые
    категории, не имеющие представления в новой папке.
    """
    ids: set[int] = set()
    for cat_dir in _iter_category_dirs():
        config_path = cat_dir / "config.json"
        if not config_path.exists():
            continue
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            cid = cfg.get("id")
            if isinstance(cid, int):
                ids.add(cid)
        except Exception:
            continue
    return ids


def get_existing_course_ids_from_fs() -> set[int]:
    """
    Вернуть множество ID курсов, для которых существуют папки курса с config.json.
    """
    ids: set[int] = set()
    for cat_dir in _iter_category_dirs():
        for entry in cat_dir.iterdir():
            if not entry.is_dir() or not entry.name.startswith("course-"):
                continue
            config_path = entry / "config.json"
            if not config_path.exists():
                continue
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                cid = cfg.get("id")
                if isinstance(cid, int):
                    ids.add(cid)
            except Exception:
                continue
    return ids


def get_existing_lesson_ids_from_fs() -> set[int]:
    """
    Вернуть множество ID уроков, для которых существуют папки уроков с config.json.
    """
    ids: set[int] = set()
    for cat_dir in _iter_category_dirs():
        for course_dir in cat_dir.iterdir():
            if not course_dir.is_dir() or not course_dir.name.startswith("course-"):
                continue
            for lesson_dir in course_dir.iterdir():
                if not lesson_dir.is_dir() or not lesson_dir.name.startswith("lesson-"):
                    continue
                config_path = lesson_dir / "config.json"
                if not config_path.exists():
                    continue
                try:
                    with open(config_path, "r", encoding="utf-8") as f:
                        cfg = json.load(f)
                    lid = cfg.get("id")
                    if isinstance(lid, int):
                        ids.add(lid)
                except Exception:
                    continue
    return ids


def get_path_identifier(category_title: str, course_title: Optional[str] = None, lesson_title: Optional[str] = None) -> str:
    """
    Генерация идентификатора пути для категории/курса/урока.
    
    Args:
        category_title: Название категории
        course_title: Название курса (опционально)
        lesson_title: Название урока (опционально)
    
    Returns:
        Идентификатор пути для использования в URL (с прямыми слешами), например: 'category-microsoft' или 'category-microsoft/course-word' или 'category-microsoft/course-word/lesson-5'
    """
    category_slug = slugify(category_title, max_length=50)
    path_parts = [f"category-{category_slug}"]
    
    if course_title:
        course_slug = slugify(course_title, max_length=50)
        path_parts.append(f"course-{course_slug}")
    
    if lesson_title:
        lesson_slug = slugify(lesson_title, max_length=50)
        path_parts.append(f"lesson-{lesson_slug}")
    
    # Возвращаем с прямыми слешами для использования в URL
    return '/'.join(path_parts)


def get_category_path(category_title: str) -> str:
    """Получить путь к папке категории (для файловой системы)."""
    path_id = get_path_identifier(category_title)
    path_parts = path_id.split('/')
    return os.path.join(get_base_categories_data_path(), *path_parts)


def get_course_path(category_title: str, course_title: str) -> str:
    """Получить путь к папке курса (для файловой системы)."""
    path_id = get_path_identifier(category_title, course_title)
    path_parts = path_id.split('/')
    return os.path.join(get_base_categories_data_path(), *path_parts)


def get_lesson_path(category_title: str, course_title: str, lesson_title: str) -> str:
    """Получить путь к папке урока (для файловой системы)."""
    # get_path_identifier возвращает путь с прямыми слешами для URL
    # Преобразуем в путь для файловой системы
    path_id = get_path_identifier(category_title, course_title, lesson_title)
    # Заменяем прямые слеши на разделители файловой системы
    path_parts = path_id.split('/')
    return os.path.join(get_base_categories_data_path(), *path_parts)


def ensure_categories_data_directory():
    """
    Создать базовую папку categories-data, если её нет.
    
    При использовании внешнего CONTENT_ROOT_DIR в корне также создаётся
    markdown-файл с инструкцией для пользователя, как работать с контентом.
    """
    os.makedirs(get_base_categories_data_path(), exist_ok=True)

    # Если используется внешний CONTENT_ROOT_DIR и он пока пустой,
    # а legacy-папка внутри проекта существует и не пуста — переносим
    # оттуда содержимое один раз. Это готовит проект к полному удалению
    # старой директории categories-data в корне.
    #
    # Но при runtime-смене корня через админ PUT (override-файл) автокопирование
    # ломает ожидания: пользователь ожидает, что увидит контент именно из
    # выбранной пустой папки. Поэтому legacy-копирование отключаем при override.
    override_active = False
    try:
        override_active = os.path.exists(_OVERRIDE_FILE)
    except Exception:
        override_active = False

    if is_external_content_root() and not override_active:
        try:
            target = Path(get_base_categories_data_path())
            legacy = Path(LEGACY_CATEGORIES_DATA_PATH)
            if legacy.exists() and legacy.is_dir():
                # Проверяем, что целевая папка фактически пуста
                if not any(target.iterdir()):
                    for item in legacy.iterdir():
                        dest = target / item.name
                        if item.is_dir():
                            if dest.exists():
                                continue
                            shutil.copytree(item, dest)
                        else:
                            if dest.exists():
                                continue
                            shutil.copy2(item, dest)
        except Exception as e:
            pass

    # Если корень задан явно и README ещё не создан — создаём подсказку.
    # Делаем это один раз, чтобы не перезаписывать возможные правки пользователя.
    env_root = _get_env_root()
    if env_root:
        readme_path = os.path.join(get_base_categories_data_path(), "CONTENT_README.md")
        marker = "<!-- LEARNSITESV_CONTENT_README_GENERATED -->"

        # Перезаписываем README, если:
        # 1) файла ещё нет
        # 2) это “наш” сгенерированный файл (по маркеру)
        # 3) файл выглядит как прошлый шаблон (начинается с заголовка). Это нужно, чтобы
        #    обновления текста применялись даже если маркера раньше не было.
        should_write = True
        if os.path.exists(readme_path):
            try:
                with open(readme_path, "r", encoding="utf-8") as rf:
                    existing = rf.read()
                should_write = (marker in existing) or existing.lstrip().startswith("# Хранилище контента уроков")
            except Exception:
                should_write = True

        if should_write:
            try:
                with open(readme_path, "w", encoding="utf-8") as f:
                    f.write(
                        "# Хранилище контента уроков\n"
                        f"{marker}\n\n"
                        "Этот каталог используется приложением LearningSite для хранения учебного контента: "
                        "категорий, курсов и уроков.\n\n"
                        "Важно: приложение читает `config.json` и файлы блоков напрямую. "
                        "База данных в основном отвечает за пользователей, роли и прогресс.\n\n"
                        "## Как управлять контентом (рекомендуется)\n\n"
                        "1. Категории / курсы / уроки: создавайте, переименовывайте, меняйте порядок и доступность "
                        "через админ‑панель сайта.\n"
                        "2. Тексты, вложения, тесты: редактируйте через админ‑панель, а не вручную.\n\n"
                        "Тем не менее, ниже описано, как устроены все JSON‑файлы и что они означают — "
                        "чтобы вы могли понять структуру и при необходимости аккуратно поправить вручную.\n\n"
                        "## Структура папок\n\n"
                        "- `category-*/config.json` — настройки категории.\n"
                        "- `category-*/course-*/config.json` — настройки курса.\n"
                        "- `category-*/course-*/lesson-*/config.json` — настройки урока.\n"
                        "- `category-*/course-*/lesson-*/texts/block-<id>.txt` — текстовые блоки урока (`heading`/`text`).\n"
                        "- `category-*/course-*/lesson-*/images/` — файлы для блоков `image`.\n"
                        "- `category-*/course-*/lesson-*/videos/` — файлы для блоков `video`.\n"
                        "- `category-*/course-*/lesson-*/files/` — файлы для блоков `file`.\n"
                        "- `category-*/course-*/lesson-*/tests/block-<id>/config.json` — настройки теста.\n"
                        "- `category-*/course-*/lesson-*/tests/block-<id>/questions/qXXX.txt` — вопросы теста.\n"
                        "- `category-*/course-*/lesson-*/blocks.json` — список блоков урока (служебный).\n\n"
                        "## Какие поля есть в `config.json`\n\n"
                        "### `category-*/config.json`\n"
                        "Минимально важные поля:\n"
                        "- `id` (int) — ID категории в БД.\n"
                        "- `title` (string) — название категории.\n"
                        "- `path_identifier` (string) — идентификатор пути (обычно формируется автоматически из названия).\n"
                        "- `type` (string) — всегда `\"category\"`.\n"
                        "Часто используются:\n"
                        "- `description` (string, может отсутствовать).\n"
                        "- `order` (int/float) — порядок показа.\n"
                        "- `sequential_progression` (bool) — последовательное прохождение уроков в курсе.\n"
                        "- `is_active` (bool) — показывать или скрывать.\n\n"
                        "Пример (примерные поля):\n"
                        "```json\n"
                        "{\n"
                        "  \"id\": 1,\n"
                        "  \"title\": \"Математика\",\n"
                        "  \"path_identifier\": \"category-matematika\",\n"
                        "  \"type\": \"category\",\n"
                        "  \"description\": \"...\",\n"
                        "  \"order\": 1,\n"
                        "  \"sequential_progression\": false,\n"
                        "  \"is_active\": true\n"
                        "}\n"
                        "```\n\n"
                        "### `category-*/course-*/config.json`\n"
                        "- `id` (int)\n"
                        "- `title` (string)\n"
                        "- `category_title` (string)\n"
                        "- `path_identifier` (string)\n"
                        "- `type` — `\"course\"`\n"
                        "Часто используются:\n"
                        "- `description` (string)\n"
                        "- `order` (int/float)\n"
                        "- `sequential_progression` (bool)\n"
                        "- `total_lessons` (int)\n"
                        "- `is_active` (bool)\n\n"
                        "### `category-*/course-*/lesson-*/config.json`\n"
                        "- `id` (int)\n"
                        "- `title` (string)\n"
                        "- `category_title` (string)\n"
                        "- `course_title` (string)\n"
                        "- `path_identifier` (string)\n"
                        "- `type` — `\"lesson\"`\n"
                        "Часто используются:\n"
                        "- `lesson_number` (int) — номер урока в курсе.\n"
                        "- `is_active` (bool)\n\n"
                        "## `blocks.json` — список блоков урока\n\n"
                        "`blocks.json` создаётся и поддерживается системой (через админ‑панель). "
                        "Он нужен для того, чтобы приложение знало, какие блоки есть в уроке и в каком порядке показывать.\n\n"
                        "Формат:\n"
                        "```json\n"
                        "{\n"
                        "  \"blocks\": [\n"
                        "    {\n"
                        "      \"id\": 10,\n"
                        "      \"lesson_id\": 123,\n"
                        "      \"block_type\": \"text\", \n"
                        "      \"order\": 0,\n"
                        "      \"content\": { \"text\": \"...\" }\n"
                        "    }\n"
                        "  ]\n"
                        "}\n"
                        "```\n"
                        "Поддерживаемые `block_type`:\n"
                        "- `heading`, `text` — текст берётся из `texts/block-<id>.txt`\n"
                        "- `test` — настройки и вопросы берутся из `tests/block-<id>/...`\n"
                        "- `image` — берутся ссылки/имя файла, а сами файлы лежат в `images/`\n"
                        "- `video` — файлы лежат в `videos/`\n"
                        "- `file` — файлы лежат в `files/`\n\n"
                        "Рекомендация: если хотите добавить/удалить блоки или поменять порядок — делайте это через админ‑панель. "
                        "Ручные правки `blocks.json` легко ломают синхронизацию с файлами.\n\n"
                        "## Тесты: `tests/block-<id>/config.json` и `questions/qXXX.txt`\n\n"
                        "### `tests/block-<id>/config.json`\n"
                        "Поля:\n"
                        "- `title` — название теста\n"
                        "- `enabled` (bool) — включен ли тест\n"
                        "- `pass_percent` (int) — порог прохождения\n"
                        "- `limit_attempts` (bool)\n"
                        "- `max_attempts` (int|null) — максимальное число попыток (если `limit_attempts=true`)\n"
                        "- `test_type` — `\"permanent\"` или `\"temporary\"`\n"
                        "- `available_from` / `available_until` (строки ISO, либо null) — для временных тестов\n"
                        "- `shuffle_questions` (bool)\n"
                        "- `shuffle_options` (bool)\n"
                        "- `time_limit_seconds` (int|null) — лимит времени (если используется)\n\n"
                        "Пример:\n"
                        "```json\n"
                        "{\n"
                        "  \"title\": \"Тест 1\",\n"
                        "  \"enabled\": true,\n"
                        "  \"pass_percent\": 70,\n"
                        "  \"limit_attempts\": false,\n"
                        "  \"max_attempts\": null,\n"
                        "  \"test_type\": \"permanent\",\n"
                        "  \"available_from\": null,\n"
                        "  \"available_until\": null,\n"
                        "  \"shuffle_questions\": false,\n"
                        "  \"shuffle_options\": false,\n"
                        "  \"time_limit_seconds\": null\n"
                        "}\n"
                        "```\n\n"
                        "### Формат вопроса `tests/block-<id>/questions/qXXX.txt`\n"
                        "Каждый файл `qXXX.txt` — это один вопрос.\n"
                        "Пример формата:\n"
                        "```text\n"
                        "Q: Вопрос\n"
                        "A) Вариант A\n"
                        "B) Вариант B\n"
                        "POINTS: 1\n"
                        "TYPE: single            # single|multiple|input\n"
                        "CORRECT: A              # для multiple: CORRECT: A,C\n"
                        "ACCEPTED: да, верно     # только для TYPE: input\n"
                        "```\n\n"
                        "## Если контент “пропал”\n\n"
                        "- Убедитесь, что `config.json` существует в нужных папках.\n"
                        "- Убедитесь, что `is_active=true` у категории/курса/урока.\n"
                        "- Если это внешний каталог (смена `CONTENT_ROOT_DIR`), проверьте, что структура соответствует описанной выше.\n"
                    )
            except Exception:
                pass


def sync_category(
    category_id: int,
    category_title: str,
    old_title: Optional[str] = None,
    settings: Optional[Dict[str, Any]] = None,
):
    """
    Синхронизировать папку категории.
    
    Args:
        category_id: ID категории
        category_title: Новое название категории
        old_title: Старое название (для переименования)
    """
    ensure_categories_data_directory()
    
    new_path = get_category_path(category_title)
    new_path_identifier = get_path_identifier(category_title)
    
    # Если переименовываем категорию
    if old_title and old_title != category_title:
        old_path = get_category_path(old_title)
        if os.path.exists(old_path):
            try:
                # Переименовываем папку
                os.rename(old_path, new_path)
            except Exception as e:
                # Если не удалось переименовать, создаем новую и копируем содержимое
                if not os.path.exists(new_path):
                    shutil.copytree(old_path, new_path)
                    shutil.rmtree(old_path)
    
    # Создаем папку, если её нет
    if not os.path.exists(new_path):
        os.makedirs(new_path, exist_ok=True)

    # Обновляем/создаем конфиг категории
    try:
        config_path = os.path.join(new_path, "config.json")
        config: Dict[str, Any] = {
            "id": category_id,
            "title": category_title,
            "path_identifier": new_path_identifier,
            "type": "category",
        }
        if settings:
            config.update(settings)
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
    except Exception as e:
        pass
    
    return new_path_identifier


def sync_course(
    category_title: str,
    course_id: int,
    course_title: str,
    old_title: Optional[str] = None,
    settings: Optional[Dict[str, Any]] = None,
):
    """
    Синхронизировать папку курса.
    
    Args:
        category_title: Название категории
        course_id: ID курса
        course_title: Новое название курса
        old_title: Старое название (для переименования)
    """
    ensure_categories_data_directory()
    
    category_path = get_category_path(category_title)
    new_course_path = get_course_path(category_title, course_title)
    new_path_identifier = get_path_identifier(category_title, course_title)
    
    # Убеждаемся, что папка категории существует
    if not os.path.exists(category_path):
        os.makedirs(category_path, exist_ok=True)
    
    # Если переименовываем курс
    if old_title and old_title != course_title:
        old_course_path = get_course_path(category_title, old_title)
        if os.path.exists(old_course_path):
            try:
                os.rename(old_course_path, new_course_path)
            except Exception as e:
                if not os.path.exists(new_course_path):
                    shutil.copytree(old_course_path, new_course_path)
                    shutil.rmtree(old_course_path)
    
    # Создаем папку курса, если её нет
    if not os.path.exists(new_course_path):
        os.makedirs(new_course_path, exist_ok=True)

    # Обновляем/создаем конфиг курса
    try:
        config_path = os.path.join(new_course_path, "config.json")
        config: Dict[str, Any] = {
            "id": course_id,
            "title": course_title,
            "category_title": category_title,
            "path_identifier": new_path_identifier,
            "type": "course",
        }
        if settings:
            config.update(settings)
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
    except Exception as e:
        pass
    
    return new_path_identifier


def sync_lesson(
    category_title: str,
    course_title: str,
    lesson_id: int,
    lesson_title: str,
    old_title: Optional[str] = None,
    settings: Optional[Dict[str, Any]] = None,
):
    """
    Синхронизировать папку урока и создать подпапки для контента.
    
    Args:
        category_title: Название категории
        course_title: Название курса
        lesson_id: ID урока
        lesson_title: Новое название урока
        old_title: Старое название (для переименования)
    """
    ensure_categories_data_directory()
    
    course_path = get_course_path(category_title, course_title)
    new_lesson_path = get_lesson_path(category_title, course_title, lesson_title)
    new_path_identifier = get_path_identifier(category_title, course_title, lesson_title)
    
    # Убеждаемся, что папка курса существует
    if not os.path.exists(course_path):
        os.makedirs(course_path, exist_ok=True)
    
    # Если переименовываем урок
    if old_title and old_title != lesson_title:
        old_lesson_path = get_lesson_path(category_title, course_title, old_title)
        if os.path.exists(old_lesson_path):
            try:
                os.rename(old_lesson_path, new_lesson_path)
            except Exception as e:
                if not os.path.exists(new_lesson_path):
                    shutil.copytree(old_lesson_path, new_lesson_path)
                    shutil.rmtree(old_lesson_path)
    
    # Создаем папку урока и подпапки для контента
    if not os.path.exists(new_lesson_path):
        os.makedirs(new_lesson_path, exist_ok=True)
    
    # Создаем подпапки для разных типов контента
    os.makedirs(os.path.join(new_lesson_path, "texts"), exist_ok=True)
    os.makedirs(os.path.join(new_lesson_path, "images"), exist_ok=True)
    os.makedirs(os.path.join(new_lesson_path, "videos"), exist_ok=True)
    os.makedirs(os.path.join(new_lesson_path, "files"), exist_ok=True)
    os.makedirs(os.path.join(new_lesson_path, "tests"), exist_ok=True)
    os.makedirs(os.path.join(new_lesson_path, "tests", "questions"), exist_ok=True)

    # Обновляем/создаем конфиг урока
    try:
        config_path = os.path.join(new_lesson_path, "config.json")
        config: Dict[str, Any] = {
            "id": lesson_id,
            "title": lesson_title,
            "category_title": category_title,
            "course_title": course_title,
            "path_identifier": new_path_identifier,
            "type": "lesson",
        }
        if settings:
            config.update(settings)
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
    except Exception as e:
        pass
    
    return new_path_identifier


def delete_category_folder(category_title: str):
    """Удалить папку категории со всем содержимым."""
    category_path = get_category_path(category_title)
    if os.path.exists(category_path):
        try:
            shutil.rmtree(category_path)
            return True
        except Exception as e:
            return False
    return False


def delete_course_folder(category_title: str, course_title: str):
    """Удалить папку курса со всем содержимым."""
    course_path = get_course_path(category_title, course_title)
    if os.path.exists(course_path):
        try:
            shutil.rmtree(course_path)
            return True
        except Exception as e:
            return False
    return False


def delete_lesson_folder(category_title: str, course_title: str, lesson_title: str):
    """Удалить папку урока со всем содержимым."""
    lesson_path = get_lesson_path(category_title, course_title, lesson_title)
    if os.path.exists(lesson_path):
        try:
            shutil.rmtree(lesson_path)
            return True
        except Exception as e:
            return False
    return False


def save_text_content(lesson_path: str, block_id: int, text_content: str):
    """Сохранить текстовый контент в файл."""
    texts_dir = os.path.join(lesson_path, 'texts')
    os.makedirs(texts_dir, exist_ok=True)
    
    text_file = os.path.join(texts_dir, f'block-{block_id}.txt')
    with open(text_file, 'w', encoding='utf-8') as f:
        f.write(text_content)
    
    return text_file


def save_image_content(lesson_path: str, block_id: int, image_url: str, image_data: bytes = None):
    """
    Сохранить изображение.
    
    Args:
        lesson_path: Путь к папке урока
        block_id: ID блока контента
        image_url: URL изображения (для скачивания)
        image_data: Данные изображения (если уже скачаны)
    
    Returns:
        Путь к сохраненному файлу
    """
    images_dir = os.path.join(lesson_path, 'images')
    os.makedirs(images_dir, exist_ok=True)
    
    # Определяем расширение из URL или используем .jpg по умолчанию
    ext = '.jpg'
    if image_url:
        ext = os.path.splitext(image_url)[1] or '.jpg'
    
    image_file = os.path.join(images_dir, f'block-{block_id}{ext}')
    
    if image_data:
        with open(image_file, 'wb') as f:
            f.write(image_data)
    # Если данных нет, файл нужно будет скачать отдельно
    
    return image_file


def save_video_content(lesson_path: str, block_id: int, video_url: str, video_data: bytes = None):
    """Сохранить видео."""
    videos_dir = os.path.join(lesson_path, 'videos')
    os.makedirs(videos_dir, exist_ok=True)
    
    ext = '.mp4'
    if video_url:
        ext = os.path.splitext(video_url)[1] or '.mp4'
    
    video_file = os.path.join(videos_dir, f'block-{block_id}{ext}')
    
    if video_data:
        with open(video_file, 'wb') as f:
            f.write(video_data)
    
    return video_file


def save_file_content(lesson_path: str, block_id: int, filename: str, file_data: bytes):
    """Сохранить файл."""
    files_dir = os.path.join(lesson_path, 'files')
    os.makedirs(files_dir, exist_ok=True)
    
    file_path = os.path.join(files_dir, filename)
    with open(file_path, 'wb') as f:
        f.write(file_data)
    
    return file_path


def get_lesson_content_path(category_title: str, course_title: str, lesson_title: str, content_type: str, filename: str = None) -> str:
    """
    Получить путь к файлу контента урока.
    
    Args:
        category_title: Название категории
        course_title: Название курса
        lesson_title: Название урока
        content_type: Тип контента ('texts', 'images', 'videos', 'files')
        filename: Имя файла (опционально)
    
    Returns:
        Путь к файлу
    """
    lesson_path = get_lesson_path(category_title, course_title, lesson_title)
    content_dir = os.path.join(lesson_path, content_type)
    
    if filename:
        return os.path.join(content_dir, filename)
    
    return content_dir


def sync_all_categories_from_db(session):
    """
    Полная синхронизация файловой структуры из базы данных.
    
    1) Создает/обновляет папки категорий/курсов/уроков и их config.json.
    2) Для всех текстовых блоков уроков создаёт/обновляет соответствующие
       .txt-файлы в подпапке texts/.
    Используется для первоначальной настройки или восстановления.
    """
    from database.models import Category, Course, Lesson, LessonContentBlock
    import json as _json
    
    ensure_categories_data_directory()
    
    categories = session.query(Category).filter(Category.is_active == True).all()
    
    from pathlib import Path
    from backend.utils.lesson_blocks_fs import write_blocks as fs_write_blocks  # type: ignore
    from backend.utils.test_fs import (  # type: ignore
        ensure_test_dirs,
        write_test_config,
        write_questions_to_dir,
        FsTestConfig,
    )

    for category in categories:
        cat_settings = {
            "description": category.description,
            "order": category.order,
            "sequential_progression": category.sequential_progression,
            "is_active": category.is_active,
        }
        sync_category(category.id, category.title, settings=cat_settings)
        
        courses = session.query(Course).filter(
            Course.category_id == category.id,
            Course.is_active == True
        ).all()
        
        for course in courses:
            course_settings = {
                "description": course.description,
                "order": course.order,
                "sequential_progression": course.sequential_progression,
                "total_lessons": course.total_lessons,
                "is_active": course.is_active,
            }
            sync_course(category.title, course.id, course.title, settings=course_settings)
            
            lessons = session.query(Lesson).filter(
                Lesson.course_id == course.id,
                Lesson.is_active == True
            ).all()
            
            for lesson in lessons:
                lesson_settings = {
                    "lesson_number": lesson.lesson_number,
                    "is_active": lesson.is_active,
                }
                sync_lesson(category.title, course.title, lesson.id, lesson.title, settings=lesson_settings)
                
                lesson_path = get_lesson_path(category.title, course.title, lesson.title)

                # Экспорт ВСЕХ блоков урока в blocks.json + вспомогательные файлы
                all_blocks = session.query(LessonContentBlock).filter(
                    LessonContentBlock.lesson_id == lesson.id,
                ).order_by(LessonContentBlock.order.asc()).all()

                blocks_for_fs = []
                for block in all_blocks:
                    try:
                        content_dict = _json.loads(block.content or "{}")
                    except Exception:
                        content_dict = {}

                    # Тексты — в файл, но сохраняем флаг html/text в blocks.json для правильного чтения
                    if block.block_type in ("heading", "text"):
                        text_value = (content_dict.get("text") or content_dict.get("html") or "")
                        if isinstance(text_value, str):
                            save_text_content(lesson_path, block.id, text_value)

                    # Тест — в tests/block-<id>/
                    if block.block_type == "test":
                        try:
                            title = str(content_dict.get("title") or "Тест")
                            settings = content_dict.get("settings") if isinstance(content_dict.get("settings"), dict) else {}
                            questions = content_dict.get("questions") if isinstance(content_dict.get("questions"), list) else []

                            tests_dir = ensure_test_dirs(lesson_path)
                            test_dir = os.path.join(tests_dir, f"block-{block.id}")
                            os.makedirs(os.path.join(test_dir, "questions"), exist_ok=True)

                            cfg = FsTestConfig(
                                title=title,
                                enabled=True,
                                pass_percent=int(settings.get("pass_percent") or 70),
                                limit_attempts=bool(settings.get("limit_attempts")),
                                max_attempts=int(settings.get("max_attempts")) if settings.get("max_attempts") else None,
                                test_type="temporary" if (settings.get("available_from") or settings.get("available_until")) else "permanent",
                                available_from=settings.get("available_from") if isinstance(settings.get("available_from"), str) else None,
                                available_until=settings.get("available_until") if isinstance(settings.get("available_until"), str) else None,
                                shuffle_questions=bool(settings.get("shuffle_questions")),
                                shuffle_options=bool(settings.get("shuffle_options")),
                            )
                            write_test_config(test_dir, cfg)
                            write_questions_to_dir(os.path.join(test_dir, "questions"), [q for q in questions if isinstance(q, dict)])

                            content_dict = {"title": title}
                        except Exception:
                            content_dict = {"title": "Тест"}

                    blocks_for_fs.append({
                        "id": block.id,
                        "lesson_id": lesson.id,
                        "block_type": block.block_type,
                        "order": block.order,
                        "content": content_dict if isinstance(content_dict, dict) else {},
                    })

                try:
                    fs_write_blocks(Path(lesson_path), blocks_for_fs)
                except Exception:
                    pass


