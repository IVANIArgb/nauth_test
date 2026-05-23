from auth.ad_ps_output import decode_powershell_stdout


def test_decode_utf8():
    raw = '{"sur_name": "Иванов"}'.encode("utf-8")
    assert "Иванов" in decode_powershell_stdout(raw)
