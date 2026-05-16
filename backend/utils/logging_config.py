"""
Классификация логов по формату [LEVEL]-CATEGORY.

Категории:
  - INFO     — информационные сообщения
  - ATTEMPT  — попытки (аутентификация, загрузка и т.д.)
  - WARN     — предупреждения
  - BUG      — баги, неожиданное поведение
  - ERROR    — ошибки
  - CRITICAL — критичные ошибки
"""

import logging
import logging.handlers
import os
import shutil
import sys
from pathlib import Path


# Категории для классификации логов
LOG_CATEGORY_INFO = "INFO"
LOG_CATEGORY_ATTEMPT = "ATTEMPT"
LOG_CATEGORY_WARN = "WARN"
LOG_CATEGORY_BUG = "BUG"
LOG_CATEGORY_ERROR = "ERROR"
LOG_CATEGORY_CRITICAL = "CRITICAL"


class ClassifiedLogFormatter(logging.Formatter):
    """
    Форматтер логов в виде [LEVEL]-CATEGORY.
    Пример: 2025-02-01 12:00:00 [ERROR]-BUG backend.api - Unexpected state
    """

    # Маппинг уровня по умолчанию → категория (если extra не передан)
    DEFAULT_CATEGORY = {
        "DEBUG": LOG_CATEGORY_INFO,
        "INFO": LOG_CATEGORY_INFO,
        "WARNING": LOG_CATEGORY_WARN,
        "ERROR": LOG_CATEGORY_ERROR,
        "CRITICAL": LOG_CATEGORY_CRITICAL,
    }

    def __init__(self, fmt=None, datefmt=None, style="%"):
        if fmt is None:
            # Сначала тип [LEVEL]-CATEGORY, потом дата, затем модуль и сообщение
            fmt = "[%(levelname)s]-%(log_category)s | %(asctime)s | %(name)s - %(message)s"
        super().__init__(fmt=fmt, datefmt=datefmt, style=style)

    def format(self, record: logging.LogRecord) -> str:
        record.log_category = getattr(
            record, "log_category", self.DEFAULT_CATEGORY.get(record.levelname, record.levelname)
        )
        return super().format(record)


class ClassifiedLoggerAdapter(logging.LoggerAdapter):
    """
    Адаптер логгера с методами по категориям: info, attempt, bug, error, critical, warning.
    """

    def process(self, msg, kwargs):
        extra = kwargs.get("extra", {})
        extra.update(self.extra)
        kwargs["extra"] = extra
        return msg, kwargs

    def info(self, msg, *args, **kwargs):
        kwargs.setdefault("extra", {})["log_category"] = LOG_CATEGORY_INFO
        self.logger.info(msg, *args, **kwargs)

    def attempt(self, msg, *args, **kwargs):
        """Попытка действия (аутентификация, загрузка и т.д.)."""
        kwargs.setdefault("extra", {})["log_category"] = LOG_CATEGORY_ATTEMPT
        self.logger.info(msg, *args, **kwargs)

    def bug(self, msg, *args, **kwargs):
        """Баг или неожиданное поведение."""
        kwargs.setdefault("extra", {})["log_category"] = LOG_CATEGORY_BUG
        self.logger.error(msg, *args, **kwargs)

    def error(self, msg, *args, **kwargs):
        """Ошибка."""
        kwargs.setdefault("extra", {})["log_category"] = LOG_CATEGORY_ERROR
        self.logger.error(msg, *args, **kwargs)

    def critical(self, msg, *args, **kwargs):
        """Критичная ошибка."""
        kwargs.setdefault("extra", {})["log_category"] = LOG_CATEGORY_CRITICAL
        self.logger.critical(msg, *args, **kwargs)

    def warning(self, msg, *args, **kwargs):
        """Предупреждение."""
        kwargs.setdefault("extra", {})["log_category"] = LOG_CATEGORY_WARN
        self.logger.warning(msg, *args, **kwargs)


def get_classified_logger(name: str) -> ClassifiedLoggerAdapter:
    """Получить логгер с классификацией по категориям."""
    return ClassifiedLoggerAdapter(logging.getLogger(name), {})


def log_with_category(logger, level: str, category: str, msg: str, *args, **kwargs):
    """
    Записать лог с указанной категорией (для стандартного logger).
    Пример: log_with_category(logger, 'error', LOG_CATEGORY_BUG, 'Unexpected state')
    """
    extra = kwargs.get("extra", {})
    extra["log_category"] = category
    kwargs["extra"] = extra
    getattr(logger, level.lower())(msg, *args, **kwargs)


class WindowsSafeRotatingFileHandler(logging.handlers.RotatingFileHandler):
    """
    RotatingFileHandler с безопасной ротацией для Windows.
    Использует копирование и удаление вместо переименования для избежания PermissionError.
    """
    
    def doRollover(self):
        """
        Переопределяем doRollover для безопасной работы на Windows.
        Обрабатывает PermissionError и продолжает работу, если ротация не удалась.
        """
        if self.stream:
            self.stream.close()
            self.stream = None
        
        # Проверяем, нужно ли делать ротацию
        if self.maxBytes > 0:
            try:
                if os.path.exists(self.baseFilename):
                    file_size = os.path.getsize(self.baseFilename)
                    if file_size >= self.maxBytes:
                        # Делаем ротацию
                        try:
                            self._safe_rotate()
                        except (OSError, IOError, PermissionError) as e:
                            # Если ротация не удалась (файл занят), просто продолжаем писать в текущий файл
                            # Это лучше, чем падать с ошибкой
                            pass
            except (OSError, IOError, PermissionError) as e:
                # Если не удалось проверить размер, просто продолжаем
                pass
        
        # Открываем файл заново
        if not self.stream:
            try:
                self.stream = self._open()
            except (OSError, IOError, PermissionError):
                # Если не удалось открыть файл, просто продолжаем без файлового логирования
                pass
    
    def _safe_rotate(self):
        """
        Безопасная ротация файлов для Windows.
        Использует копирование и удаление вместо переименования.
        Обрабатывает все ошибки и продолжает работу, если ротация не удалась.
        """
        if self.backupCount > 0:
            try:
                # Удаляем самый старый файл
                s = f"{self.baseFilename}.{self.backupCount}"
                if os.path.exists(s):
                    try:
                        os.remove(s)
                    except (OSError, IOError, PermissionError):
                        pass
                
                # Сдвигаем существующие файлы
                for i in range(self.backupCount - 1, 0, -1):
                    sfn = f"{self.baseFilename}.{i}"
                    dfn = f"{self.baseFilename}.{i + 1}"
                    if os.path.exists(sfn):
                        if os.path.exists(dfn):
                            try:
                                os.remove(dfn)
                            except (OSError, IOError, PermissionError):
                                pass
                        try:
                            # Используем копирование вместо переименования
                            shutil.copy2(sfn, dfn)
                            # Пытаемся удалить исходный файл (может не получиться, если он открыт)
                            try:
                                os.remove(sfn)
                            except (OSError, IOError, PermissionError):
                                # Если не удалось удалить, это нормально - файл может быть открыт
                                pass
                        except (OSError, IOError, PermissionError):
                            pass
                
                # Копируем текущий файл в .1
                dfn = f"{self.baseFilename}.1"
                if os.path.exists(self.baseFilename):
                    try:
                        if os.path.exists(dfn):
                            try:
                                os.remove(dfn)
                            except (OSError, IOError, PermissionError):
                                pass
                        shutil.copy2(self.baseFilename, dfn)
                        # Пытаемся очистить текущий файл
                        try:
                            with open(self.baseFilename, 'w', encoding=self.encoding):
                                pass
                        except (OSError, IOError, PermissionError):
                            # Если не удалось очистить, просто продолжаем
                            pass
                    except (OSError, IOError, PermissionError):
                        # Если не удалось скопировать, просто продолжаем без ротации
                        pass
            except Exception:
                # Если произошла любая ошибка, просто продолжаем без ротации
                # Это лучше, чем падать с ошибкой
                pass


def configure_logging(app) -> None:
    """Configure basic logging for the application."""
    log_dir = Path(app.config.get("PROJECT_ROOT", Path.cwd())) / "backend" / "logs"
    log_file = log_dir / "app.log"
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    
    # Clear existing handlers
    for handler in list(root_logger.handlers):
        root_logger.removeHandler(handler)
    
    # Формат [LEVEL]-CATEGORY
    classified_formatter = ClassifiedLogFormatter(
        fmt="[%(levelname)s]-%(log_category)s | %(asctime)s | %(name)s - %(message)s"
    )

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(classified_formatter)
    root_logger.addHandler(console_handler)

    # File handler (best-effort). In read-only environments (like Docker with RO mount),
    # gracefully skip file logging and keep console only.
    try:
        log_dir.mkdir(parents=True, exist_ok=True)

        # Используем безопасный обработчик для Windows
        if sys.platform == 'win32':
            file_handler = WindowsSafeRotatingFileHandler(
                log_file, maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8"
            )
        else:
            file_handler = logging.handlers.RotatingFileHandler(
                log_file, maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8"
            )

        file_handler.setLevel(logging.INFO)
        file_handler.setFormatter(classified_formatter)
        root_logger.addHandler(file_handler)
    except OSError:
        # Fall back to console-only logging when filesystem is not writable
        pass




