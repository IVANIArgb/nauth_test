import os
import sys
import socket

if len(sys.argv) > 1 and sys.argv[1] == "seed":
    import seed_test_data

    seed_test_data.main()
    sys.exit(0)

def _env_bool(name: str, default: bool = False) -> bool:
    val = os.environ.get(name)
    if val is None:
        return default
    return str(val).strip().lower() in ("true", "1", "yes", "y", "on")


def _is_docker() -> bool:
    return _env_bool("DOCKER", default=False)


if _is_docker() and os.name != "nt":
    for _dir in ("/app/database", "/app/categories-data", "/app/backups"):
        try:
            os.makedirs(_dir, exist_ok=True)
        except OSError:
            pass

test_mode = _env_bool("TEST_MODE", default=False)
db_recreate_on_start = _env_bool("DB_RECREATE_ON_START", default=False)
db_seed_on_start = _env_bool("DB_SEED_ON_START", default=test_mode)

if os.name != "nt":
    cr = os.environ.get("CONTENT_ROOT_DIR", "")
    cr_l = (cr or "").strip().lower()
    if not cr or cr_l.startswith("c:\\") or cr_l.startswith("c:/"):
        os.environ["CONTENT_ROOT_DIR"] = "/app/categories-data"

if os.name != "nt" and _is_docker():
    _cr = os.environ.get("CONTENT_ROOT_DIR", "").strip()
    if _cr and not os.path.isdir(_cr):
        _fb = "/app/categories-data"
        os.makedirs(_fb, exist_ok=True)
        os.environ["CONTENT_ROOT_DIR"] = _fb
        print(
            f"WARNING: CONTENT_ROOT_DIR ({_cr}) недоступен, "
            f"используется {_fb}. Проверьте volumes в docker-compose."
        )

from backend import create_app

env_name = os.environ.get("FLASK_ENV", "development")
host = os.environ.get("HOST", "127.0.0.1")
port = int(os.environ.get("PORT", "5000"))

if env_name.strip().lower() == "development" and "DEBUG" not in os.environ:
    os.environ["DEBUG"] = "true"


def _is_port_busy(bind_host: str, bind_port: int) -> bool:
    """Проверка, занят ли TCP-порт локально."""
    probe_host = "127.0.0.1" if bind_host in ("0.0.0.0", "::") else bind_host
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.4)
        return s.connect_ex((probe_host, bind_port)) == 0

run_with_gunicorn = os.environ.get("RUN_WITH_GUNICORN", "").strip().lower() in (
    "true",
    "1",
    "yes",
    "y",
    "on",
)
workers = os.environ.get("GUNICORN_WORKERS", "").strip()
threads = os.environ.get("GUNICORN_THREADS", "").strip()

if os.name == "nt" and run_with_gunicorn:
    print("INFO: RUN_WITH_GUNICORN=true, но Windows не поддерживается gunicorn. Используем Flask dev server.")
    run_with_gunicorn = False

app = create_app(env_name)

if db_recreate_on_start:
    from database.recreate_databases import recreate_database
    recreate_database()

if db_seed_on_start:
    import seed_test_data
    seed_test_data.main()

if __name__ == "__main__":
    is_werkzeug_reloader_child = os.environ.get("WERKZEUG_RUN_MAIN") == "true"
    if (not is_werkzeug_reloader_child) and _is_port_busy(host, port):
        print(
            f"ERROR: Порт {port} уже занят. "
            "Остановите предыдущий сервер перед новым запуском."
        )
        sys.exit(1)

    if run_with_gunicorn:
        import shutil

        gunicorn_path = shutil.which("gunicorn")
        if not gunicorn_path:
            print("WARNING: gunicorn not found in PATH. Falling back to app.run().")
        else:
            cmd = [
                gunicorn_path,
                "-b",
                f"{host}:{port}",
                "backend.wsgi:application",
            ]
            if workers:
                cmd += ["-w", workers]
            if threads:
                cmd += ["--threads", threads]
            gunicorn_timeout = os.environ.get("GUNICORN_TIMEOUT", "120").strip()
            if gunicorn_timeout.isdigit():
                cmd += ["--timeout", gunicorn_timeout]
            cmd += ["--access-logfile", "-", "--error-logfile", "-"]

            if os.name == "nt":
                import subprocess
                subprocess.run(cmd)
            else:
                os.execvp(cmd[0], cmd)

    debug = os.environ.get("DEBUG", "false").lower() in ("true", "1", "yes")
    if os.name == "nt":
        app.run(host=host, port=port, debug=debug, use_reloader=False)
    else:
        app.run(host=host, port=port, debug=debug)
