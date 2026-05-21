"""
Утилиты для загрузки файлов.
"""
import os
import secrets
from typing import Tuple, Optional
from flask import current_app, request
from werkzeug.utils import secure_filename

# Константы
CHUNK_SIZE = 1024 * 1024  # 1MB chunks

def _detect_mime_from_bytes(head: bytes) -> Optional[str]:
    if len(head) < 4:
        return None
    if head.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if head[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if head[:6] in (b"GIF87a", b"GIF89a"):
        return "image/gif"
    if len(head) >= 12 and head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "image/webp"
    if head.startswith(b"%PDF"):
        return "application/pdf"
    if head[:4] == b"PK\x03\x04":
        return "application/zip"
    return None


def _read_file_header(file, nbytes: int = 32) -> bytes:
    pos = file.tell() if hasattr(file, "tell") else None
    try:
        if hasattr(file, "seek"):
            file.seek(0)
        chunk = file.read(nbytes) if hasattr(file, "read") else b""
        if hasattr(file, "seek") and pos is not None:
            file.seek(pos)
        elif hasattr(file, "seek"):
            file.seek(0)
        return chunk or b""
    except Exception:
        return b""


def validate_file_size(file, max_size: Optional[int] = None) -> Tuple[bool, Optional[str]]:
    """
    Валидировать размер файла.
    
    Args:
        file: Файл из request.files
        max_size: Максимальный размер в байтах (если None, берется из конфига)
        
    Returns:
        Tuple[bool, Optional[str]]: (is_valid, error_message)
    """
    if max_size is None:
        max_size = current_app.config.get('MAX_CONTENT_LENGTH', 1024 * 1024 * 1024)  # 1GB по умолчанию
    
    if hasattr(file, 'content_length') and file.content_length and file.content_length > max_size:
        max_size_mb = max_size // (1024 * 1024)
        max_size_gb = max_size_mb / 1024
        if max_size_gb >= 1:
            return False, f'Файл слишком большой. Максимальный размер: {max_size_gb:.1f} GB'
        else:
            return False, f'Файл слишком большой. Максимальный размер: {max_size_mb} MB'
    
    return True, None


def validate_file_extension(filename: str) -> Tuple[bool, Optional[str]]:
    """
    Валидировать расширение файла.
    
    Args:
        filename: Имя файла
        
    Returns:
        Tuple[bool, Optional[str]]: (is_valid, error_message)
    """
    ext = os.path.splitext(filename)[1].lower()
    forbidden_extensions = current_app.config.get('FORBIDDEN_EXTENSIONS', set())
    
    if ext in forbidden_extensions:
        return False, f'Загрузка файлов с расширением {ext} запрещена'
    
    return True, None


def validate_mime_type(file, allowed_types: Optional[list] = None) -> Tuple[bool, Optional[str]]:
    """
    Валидировать MIME тип файла.
    
    Args:
        file: Файл из request.files
        allowed_types: Список разрешенных MIME типов (если None, берется из конфига)
        
    Returns:
        Tuple[bool, Optional[str]]: (is_valid, warning_message)
    """
    mime_type = file.mimetype or 'application/octet-stream'
    detected = _detect_mime_from_bytes(_read_file_header(file))
    if detected and detected != mime_type:
        mime_type = detected

    if allowed_types is None:
        allowed_types = current_app.config.get('ALLOWED_MIME_TYPES', {}).get('files', [])

    if allowed_types and mime_type not in allowed_types:
        return False, f'Тип файла {mime_type} не разрешен. Разрешенные типы: {", ".join(allowed_types)}'

    if detected and allowed_types and detected not in allowed_types:
        return False, f"Содержимое файла ({detected}) не входит в разрешённые типы"

    return True, None


def save_file_streaming(file, upload_dir: str, max_size: Optional[int] = None) -> Tuple[Optional[str], Optional[str], int]:
    """
    Сохранить файл потоково для поддержки больших файлов.
    
    Args:
        file: Файл из request.files
        upload_dir: Директория для сохранения
        max_size: Максимальный размер в байтах
        
    Returns:
        Tuple[Optional[str], Optional[str], int]: (file_path, error_message, file_size)
        Если ошибка, file_path будет None, а error_message будет содержать описание ошибки
    """
    if max_size is None:
        max_size = current_app.config.get('MAX_CONTENT_LENGTH', 1024 * 1024 * 1024)
    
    # Создаем директорию, если её нет
    os.makedirs(upload_dir, exist_ok=True)
    
    # Генерируем безопасное имя файла
    original_filename = secure_filename(file.filename)
    ext = os.path.splitext(original_filename)[1].lower()
    stored_filename = f"{secrets.token_hex(16)}{ext}"
    file_path = os.path.join(upload_dir, stored_filename)
    
    total_written = 0
    
    try:
        with open(file_path, 'wb') as f:
            while True:
                chunk = file.stream.read(CHUNK_SIZE)
                if not chunk:
                    break
                f.write(chunk)
                total_written += len(chunk)
                
                # Проверка размера во время загрузки
                if total_written > max_size:
                    f.close()
                    if os.path.exists(file_path):
                        os.remove(file_path)
                    max_size_mb = max_size // (1024 * 1024)
                    max_size_gb = max_size_mb / 1024
                    if max_size_gb >= 1:
                        return None, f'Файл слишком большой. Максимальный размер: {max_size_gb:.1f} GB', 0
                    else:
                        return None, f'Файл слишком большой. Максимальный размер: {max_size_mb} MB', 0
        
        # Дополнительная проверка размера после сохранения
        file_size = os.path.getsize(file_path)
        if file_size > max_size:
            os.remove(file_path)
            max_size_mb = max_size // (1024 * 1024)
            max_size_gb = max_size_mb / 1024
            if max_size_gb >= 1:
                return None, f'Файл слишком большой. Максимальный размер: {max_size_gb:.1f} GB', 0
            else:
                return None, f'Файл слишком большой. Максимальный размер: {max_size_mb} MB', 0
        
        return file_path, None, file_size
        
    except Exception as e:
        # Если произошла ошибка, удаляем частично загруженный файл
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except Exception as cleanup_error:
                pass
        return None, str(e), 0


def get_uploads_directory() -> str:
    """
    Получить путь к директории uploads.
    
    Returns:
        str: Путь к директории uploads
    """
    # Получаем путь к backend директории
    # Файл находится в backend/utils/file_upload.py
    # Нужно подняться на 2 уровня: utils -> backend
    current_file = os.path.abspath(__file__)
    utils_dir = os.path.dirname(current_file)
    backend_dir = os.path.dirname(utils_dir)
    return os.path.join(backend_dir, 'uploads')
