# Профиль из AD автоматически (без keytab, без ручного ввода в БД)

## Как это работает

1. **Доменный Windows-ПК** — при `run-server.bat` без `NAUTH_FORCE_DOCKER`:
   - запускается **нативный** Flask;
   - логин = ваша сессия Windows;
   - ФИО/отдел/должность = **Get-ADUser** / ADSI (ничего в `.env` для профиля).

2. **Docker** (`set NAUTH_FORCE_DOCKER=1`):
   - перед стартом скрипт на **хосте** читает AD и пишет `runtime/ad-cache/<логин>.json`;
   - nginx подставляет **ваш** `%USERNAME%` в `X-Remote-User` (авто в `.env`);
   - контейнер подхватывает JSON и обновляет SQLite сам.

Пользователь **не вводит** данные в базу вручную.

## Команды

```cmd
update.bat
```

или только запуск:

```cmd
run-server.bat
```

Docker принудительно:

```cmd
set NAUTH_FORCE_DOCKER=1
run-server.bat
```

## Если профиль пустой

- ПК должен быть **в домене** (`echo %USERDNSDOMAIN%`).
- Docker Desktop **запущен** (для Docker-режима).
- После смены логина: снова `run-server.bat` (обновит кэш AD).
