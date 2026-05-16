import json
import os
import re
from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class FsTestConfig:
    """Конфиг теста для FS хранения."""

    title: str = "Тест"
    enabled: bool = True
    pass_percent: int = 70
    limit_attempts: bool = False
    max_attempts: Optional[int] = None
    test_type: str = "permanent"  # permanent|temporary
    available_from: Optional[str] = None  # ISO
    available_until: Optional[str] = None  # ISO
    shuffle_questions: bool = False
    shuffle_options: bool = False
    time_limit_seconds: Optional[int] = None

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "enabled": bool(self.enabled),
            "pass_percent": int(self.pass_percent),
            "limit_attempts": bool(self.limit_attempts),
            "max_attempts": int(self.max_attempts) if self.max_attempts is not None else None,
            "test_type": self.test_type,
            "available_from": self.available_from,
            "available_until": self.available_until,
            "shuffle_questions": bool(self.shuffle_questions),
            "shuffle_options": bool(self.shuffle_options),
            "time_limit_seconds": int(self.time_limit_seconds) if self.time_limit_seconds is not None else None,
        }


_opt_re = re.compile(r"^\s*([A-ZА-Я])\)\s*(.+?)\s*$")


def ensure_test_dirs(lesson_path: str) -> str:
    tests_dir = os.path.join(lesson_path, "tests")
    questions_dir = os.path.join(tests_dir, "questions")
    os.makedirs(questions_dir, exist_ok=True)
    return tests_dir


def _parse_int(value: Any, default: int) -> int:
    try:
        n = int(value)
        return n
    except Exception:
        return default


def _parse_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        v = value.strip().lower()
        if v in ("1", "true", "yes", "y", "on"):
            return True
        if v in ("0", "false", "no", "n", "off"):
            return False
    return default


def read_test_config(tests_dir: str) -> FsTestConfig:
    cfg_path = os.path.join(tests_dir, "config.json")
    if not os.path.exists(cfg_path):
        return FsTestConfig()
    try:
        with open(cfg_path, "r", encoding="utf-8") as f:
            raw = json.load(f)
    except Exception:
        return FsTestConfig()
    if not isinstance(raw, dict):
        return FsTestConfig()

    cfg = FsTestConfig()
    cfg.title = str(raw.get("title") or cfg.title)
    cfg.enabled = _parse_bool(raw.get("enabled"), True)
    cfg.pass_percent = max(1, min(100, _parse_int(raw.get("pass_percent"), cfg.pass_percent)))
    cfg.limit_attempts = _parse_bool(raw.get("limit_attempts"), False)
    ma = raw.get("max_attempts")
    try:
        ma_i = int(ma) if ma is not None else None
        cfg.max_attempts = ma_i if (ma_i is not None and ma_i > 0) else None
    except Exception:
        cfg.max_attempts = None
    cfg.test_type = (raw.get("test_type") or cfg.test_type) if isinstance(raw.get("test_type"), str) else cfg.test_type
    cfg.available_from = raw.get("available_from") if isinstance(raw.get("available_from"), str) else None
    cfg.available_until = raw.get("available_until") if isinstance(raw.get("available_until"), str) else None
    cfg.shuffle_questions = _parse_bool(raw.get("shuffle_questions"), False)
    cfg.shuffle_options = _parse_bool(raw.get("shuffle_options"), False)

    # Лимит времени (поддерживаем оба формата: seconds или enabled+minutes)
    tl_seconds = raw.get("time_limit_seconds")
    tl_enabled = _parse_bool(raw.get("time_limit_enabled"), False)
    tl_minutes = raw.get("time_limit_minutes")
    seconds: Optional[int] = None
    try:
        if tl_seconds is not None:
            s = int(tl_seconds)
            seconds = s if s > 0 else None
        elif tl_enabled and tl_minutes is not None:
            m = int(tl_minutes)
            seconds = (m * 60) if m > 0 else None
    except Exception:
        seconds = None
    cfg.time_limit_seconds = seconds
    return cfg


def write_test_config(tests_dir: str, cfg: FsTestConfig) -> None:
    os.makedirs(tests_dir, exist_ok=True)
    cfg_path = os.path.join(tests_dir, "config.json")
    with open(cfg_path, "w", encoding="utf-8") as f:
        json.dump(cfg.to_dict(), f, ensure_ascii=False, indent=2)


def parse_question_txt(txt: str) -> dict:
    """Парсим один вопрос из txt в модель вопроса (совместимую с фронтом)."""
    lines = [ln.rstrip("\n") for ln in (txt or "").splitlines()]
    q_text = ""
    q_type: Optional[str] = None  # single|multiple|input
    points = 1
    accepted: list[str] = []
    options: list[str] = []
    correct_letters: list[str] = []

    for raw in lines:
        line = raw.strip()
        if not line:
            continue
        if line.upper().startswith("Q:"):
            q_text = line[2:].strip()
            continue
        if line.upper().startswith("TYPE:"):
            q_type = line[5:].strip().lower()
            continue
        if line.upper().startswith("POINTS:"):
            points = max(1, _parse_int(line[7:].strip(), 1))
            continue
        if line.upper().startswith("ACCEPTED:"):
            raw_acc = line[9:].strip()
            accepted = [a.strip() for a in raw_acc.split(",") if a.strip()]
            continue
        if line.upper().startswith("CORRECT:"):
            raw_corr = line[8:].strip()
            parts = [p.strip() for p in raw_corr.split(",") if p.strip()]
            correct_letters = [p.upper() for p in parts]
            continue

        m = _opt_re.match(line)
        if m:
            options.append(m.group(2).strip())

    # Нормализация типа
    if q_type == "input":
        return {
            "text": q_text,
            "answer_type": "input",
            "accepted_answers": accepted,
            "points": points,
            "multiple": False,
        }

    # letters -> indexes
    idxs = []
    for lt in correct_letters:
        # A,B,C... or А,Б,В... (русские буквы тоже поддержим)
        if len(lt) != 1:
            continue
        ch = lt[0]
        if "A" <= ch <= "Z":
            idxs.append(ord(ch) - ord("A"))
        elif "А" <= ch <= "Я":
            idxs.append(ord(ch) - ord("А"))
    idxs = [i for i in idxs if i >= 0]
    is_multiple = len(idxs) > 1 or (q_type == "multiple")
    if not q_type:
        q_type = "multiple" if is_multiple else "single"

    if is_multiple:
        return {
            "text": q_text,
            "answer_type": "multiple",
            "multiple": True,
            "options": options,
            "correct_answer": sorted(set(idxs)),
            "points": points,
        }
    return {
        "text": q_text,
        "answer_type": "single",
        "multiple": False,
        "options": options,
        "correct_answer": (idxs[0] if idxs else 0),
        "points": points,
    }


def serialize_question_txt(question: dict) -> str:
    """Сериализация вопроса в человекочитаемый txt (1 файл = 1 вопрос)."""
    q_text = str(question.get("text") or "").strip()
    answer_type = (question.get("answer_type") or ("multiple" if question.get("multiple") else "single")).lower()
    points = _parse_int(question.get("points"), 1)

    out: list[str] = []
    out.append(f"Q: {q_text}")
    out.append(f"POINTS: {max(1, points)}")

    if answer_type == "input":
        out.append("TYPE: input")
        accepted = question.get("accepted_answers") or []
        if isinstance(accepted, (list, tuple)):
            accepted_clean = [str(a).strip() for a in accepted if str(a).strip()]
        else:
            accepted_clean = []
        out.append("ACCEPTED: " + ", ".join(accepted_clean))
        return "\n".join(out) + "\n"

    options = question.get("options") or []
    if not isinstance(options, (list, tuple)):
        options = []

    for i, opt in enumerate(options):
        letter = chr(ord("A") + i)
        out.append(f"{letter}) {str(opt).strip()}")

    correct = question.get("correct_answer")
    if isinstance(correct, (list, tuple)):
        idxs = [int(x) for x in correct if isinstance(x, (int, float))]
    elif isinstance(correct, (int, float)):
        idxs = [int(correct)]
    else:
        idxs = []
    idxs = [i for i in idxs if i >= 0]
    letters = []
    for i in idxs:
        letters.append(chr(ord("A") + i))
    if answer_type == "multiple" or len(letters) > 1:
        out.append("TYPE: multiple")
    else:
        out.append("TYPE: single")
    out.append("CORRECT: " + ",".join(letters))

    return "\n".join(out) + "\n"


def read_questions_from_dir(questions_dir: str) -> list[dict]:
    if not os.path.isdir(questions_dir):
        return []
    files = [f for f in os.listdir(questions_dir) if f.lower().endswith(".txt")]
    files.sort()
    questions: list[dict] = []
    for fn in files:
        path = os.path.join(questions_dir, fn)
        try:
            with open(path, "r", encoding="utf-8") as f:
                questions.append(parse_question_txt(f.read()))
        except Exception:
            continue
    return questions


def write_questions_to_dir(questions_dir: str, questions: list[dict]) -> None:
    os.makedirs(questions_dir, exist_ok=True)
    # Полностью перезаписываем в стабильные имена q001.txt, q002.txt...
    for old in os.listdir(questions_dir):
        if old.lower().endswith(".txt"):
            try:
                os.remove(os.path.join(questions_dir, old))
            except Exception:
                pass
    for idx, q in enumerate(questions or [], start=1):
        name = f"q{idx:03d}.txt"
        path = os.path.join(questions_dir, name)
        with open(path, "w", encoding="utf-8") as f:
            f.write(serialize_question_txt(q if isinstance(q, dict) else {}))

