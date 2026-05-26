# Развёртывание LearningSiteSV

Пошаговая инструкция для переноса проекта на **Ubuntu-сервер без Docker** (рекомендуемый способ).

**Репозиторий:** https://github.com/IVANIArgb/nauth_test  
**Ветка:** `main` (или `tests` — актуальная разработка)

---

## Что понадобится на сервере

- Ubuntu 20.04+ (или Debian-подобный)
- Доступ в интернет (git, apt)
- Пользователь с `sudo` (для установки пакетов)
- Открытый порт **8000** (или свой в `.env`)

На сервере **не нужны** заранее: Git, Python, venv — скрипт установки поставит всё сам.

---

## 1. Первая установка (с нуля)

### Вариант А — клонирование с GitHub

```bash
# Каталог проекта (можно другой путь)
export NAUTH_INSTALL_DIR=$HOME/nauth_test
export NAUTH_BRANCH=main
export NAUTH_REPO=https://github.com/IVANIArgb/nauth_test.git

git clone -b "$NAUTH_BRANCH" "$NAUTH_REPO" "$NAUTH_INSTALL_DIR"
cd "$NAUTH_INSTALL_DIR"

chmod +x setup-ubuntu.sh run-server.sh update.sh
chmod +x scripts/deploy/*.sh

./setup-ubuntu.sh
```

### Вариант Б — одной командой

```bash
git clone -b main https://github.com/IVANIArgb/nauth_test.git ~/nauth_test && \
cd ~/nauth_test && \
chmod +x setup-ubuntu.sh run-server.sh update.sh && \
./setup-ubuntu.sh
```

### Что делает `setup-ubuntu.sh`

1. Ставит через `apt`: `git`, `python3`, `python3-venv`, `pip`, библиотеки для LDAP  
2. Создаёт виртуальное окружение `venv/`  
3. Устанавливает зависимости из `requirements-prod.txt`  
4. Создаёт/дополняет `.env` (см. ниже)  
5. Создаёт служебные папки (`backend/logs`, `categories-data`, …)

---

## 2. Файл `.env` (автонастройка)

После установки в корне проекта появляется `.env`. Ключевые значения по умолчанию:

| Переменная | Значение | Смысл |
|------------|----------|--------|
| `TEST_MODE` | `true` | Режим разработки: админ-права в API, seed БД, терминал |
| `TEST_MODE_AUTH_BYPASS` | `false` | **Реальная** аутентификация (Kerberos/LDAP/Windows), без подмены логина |
| `HOST` | `0.0.0.0` | Слушать все интерфейсы |
| `PORT` | `8000` | Порт сайта |
| `RUN_WITH_GUNICORN` | `true` | Продакшен-подобный сервер |
| `DB_SEED_ON_START` | `true` | Тестовые данные при первом старте |
| `KERBEROS_AUTH_ENABLED` | `true` | Kerberos включён (если есть домен) |

При необходимости отредактируйте:

```bash
nano ~/nauth_test/.env
```

Дописать недостающие ключи из шаблона автонастройки:

```bash
cd ~/nauth_test
source venv/bin/activate
python start/setup_env.py --sync-auto --skip-venv
```

Шаблоны вручную: `env.example` (полный список), для Docker — `docker/docker.env.*`.

---

## 3. Запуск сервера

```bash
cd ~/nauth_test
./run-server.sh
```

Сайт: **http://IP_СЕРВЕРА:8000/**

Остановка: `Ctrl+C` в терминале.

### Запуск в фоне (screen)

```bash
screen -S learnsite
cd ~/nauth_test
./run-server.sh
# Отсоединиться: Ctrl+A, затем D
# Вернуться: screen -r learnsite
```

### Запуск как systemd-сервис (опционально)

Создайте `/etc/systemd/system/learnsite.service`:

```ini
[Unit]
Description=LearningSiteSV
After=network.target

[Service]
Type=simple
User=ВАШ_ПОЛЬЗОВАТЕЛЬ
WorkingDirectory=/home/ВАШ_ПОЛЬЗОВАТЕЛЬ/nauth_test
EnvironmentFile=/home/ВАШ_ПОЛЬЗОВАТЕЛЬ/nauth_test/.env
ExecStart=/home/ВАШ_ПОЛЬЗОВАТЕЛЬ/nauth_test/venv/bin/python run.py
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable learnsite
sudo systemctl start learnsite
sudo systemctl status learnsite
```

---

## 4. Обновление после изменений на GitHub

```bash
cd ~/nauth_test
./update.sh
./run-server.sh
```

`update.sh` выполняет: `git pull` → обновление pip → синхронизация ключей `.env`.

---

## 5. Структура скриптов

| Путь | Назначение |
|------|------------|
| `scripts/deploy/setup-ubuntu.sh` | Первая установка |
| `scripts/deploy/run-server.sh` | Запуск |
| `scripts/deploy/update.sh` | Обновление |
| `scripts/deploy/update.bat` | Обновление на Windows |
| `setup-ubuntu.sh`, `run-server.sh`, `update.sh` в корне | Короткие обёртки → `scripts/deploy/` |

---

## 6. Windows (разработка у вас)

```powershell
cd "путь\к\LearningSiteSV"
git pull origin main
update.bat
```

`update.bat` — git pull, pip, запуск `run.py` (без Docker).

Первая настройка на Windows:

```powershell
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements-prod.txt
python start\setup_env.py --sync-auto
python run.py
```

---

## 7. Docker (опционально, не для Ubuntu-сценария коллеги)

Файлы в папке **`docker/`**. Из корня репозитория:

```bash
cp docker/docker.env.example .env
docker compose -f docker/docker-compose.yml build
docker compose -f docker/docker-compose.yml up -d
```

Подробнее: [`docker/README.md`](../../docker/README.md).

---

## 8. Проверка после установки

```bash
curl -s http://127.0.0.1:8000/healthz
curl -s http://127.0.0.1:8000/api/current-user
```

В браузере откройте главную страницу и войдите под доменной учёткой (если настроен Kerberos/LDAP).

---

## 9. Частые проблемы

| Проблема | Решение |
|---------|---------|
| `Permission denied` при `./setup-ubuntu.sh` | `chmod +x setup-ubuntu.sh run-server.sh update.sh` |
| Порт занят | В `.env` смените `PORT=8001` или остановите старый процесс |
| Нет git на сервере | `sudo apt install git` или снова `./setup-ubuntu.sh` |
| Ошибка LDAP/Kerberos | Проверьте `LDAP_*` / домен в `.env`, см. `env.example` |
| Пустая база | Убедитесь `DB_SEED_ON_START=true`, перезапустите `./run-server.sh` |

---

## 10. Переменные окружения для установки

```bash
export NAUTH_REPO=https://github.com/IVANIArgb/nauth_test.git
export NAUTH_BRANCH=main
export NAUTH_INSTALL_DIR=$HOME/nauth_test
```

---

## Краткая шпаргалка

```bash
# Установка
git clone -b main https://github.com/IVANIArgb/nauth_test.git ~/nauth_test
cd ~/nauth_test && chmod +x *.sh scripts/deploy/*.sh && ./setup-ubuntu.sh

# Запуск
./run-server.sh

# Обновление
./update.sh && ./run-server.sh
```
