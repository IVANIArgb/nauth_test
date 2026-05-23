"""Кодировка AD: починка кракозябр и UTF-8 JSON."""
from auth.encoding_utils import decode_subprocess_stdout, normalize_ad_text, repair_mojibake


def test_repair_mojibake_utf8_as_latin1():
    good = "Иванов"
    broken = good.encode("utf-8").decode("latin-1")
    assert repair_mojibake(broken) == good


def test_normalize_keeps_valid_cyrillic():
    assert normalize_ad_text("Петров") == "Петров"
    assert normalize_ad_text("  Отдел ИТ  ") == "Отдел ИТ"


def test_decode_subprocess_utf8():
    raw = '{"sur_name": "Иванов"}'.encode("utf-8")
    assert "Иванов" in decode_subprocess_stdout(raw)
