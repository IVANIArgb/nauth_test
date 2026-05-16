"""
Обратный совместимый wrapper вокруг `auth.new_auth`.

Реальная реализация `NewAuth` живёт в модуле `auth.new_auth`.
Этот файл оставлен только для поддержки старых импортов `backend.new_auth`.
"""

from auth.new_auth import NewAuth, init_new_auth

__all__ = ["NewAuth", "init_new_auth"]