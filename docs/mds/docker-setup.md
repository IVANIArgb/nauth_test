# Запуск LearnSite в Docker

## Быстрый старт (любая ОС)

```bash
docker compose build
docker compose up -d
```

Откройте http://localhost:8000 . Данные БД и контент хранятся в именованных томах Docker.

Переменные окружения можно задать через файл `.env` в корне проекта (шаблон: `docker/docker.env.example`).

## Windows + контент с рабочего стола

Если каталоги курсов лежат на Desktop (например `Desktop/learning-content`):

```bash
docker compose -f docker/docker-compose.yml -f docker/docker-compose.windows.yml up -d
```

## Полезные переменные

| Переменная | Описание |
|------------|----------|
| `DB_SEED_ON_START=true` | Заполнить БД демо-данными при старте |
| `TEST_MODE=true` | Режим «все админы» (только для закрытых контуров) |
| `FLASK_ENV=production` | Продакшен-режим; обязательно задайте надёжный `SECRET_KEY` |
| `GUNICORN_WORKERS` | Число воркеров (по умолчанию 2) |
| `GUNICORN_TIMEOUT` | Таймаут запроса в секундах (по умолчанию 120) |

## Сборка с дополнительным индексом PyPI

```bash
docker build --build-arg PIP_EXTRA_INDEX_URL=https://pypi.org/simple -t learnsite:web .
```
