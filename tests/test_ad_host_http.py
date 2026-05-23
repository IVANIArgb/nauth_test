"""AD profile from Windows host HTTP API."""
import json
from unittest.mock import patch

from auth.ad_host_http import get_user_info_from_host_http


def test_host_http_empty_without_url():
    with patch.dict("os.environ", {}, clear=False):
        assert get_user_info_from_host_http("ivanov") is None


def test_host_http_parses_profile():
    body = json.dumps(
        {
            "first_name": "Иван",
            "second_name": "Иванович",
            "sur_name": "Иванов",
            "department": "IT",
            "position": "Engineer",
        }
    ).encode("utf-8")

    class Resp:
        def read(self):
            return body

        def __enter__(self):
            return self

        def __exit__(self, *a):
            pass

    with patch.dict("os.environ", {"AD_HOST_PROFILE_URL": "http://127.0.0.1:18080"}):
        with patch("urllib.request.urlopen", return_value=Resp()):
            out = get_user_info_from_host_http("ivanov")
    assert out["sur_name"] == "Иванов"
    assert out["department"] == "IT"


def test_host_http_rejects_bad_login():
    with patch.dict("os.environ", {"AD_HOST_PROFILE_URL": "http://127.0.0.1:18080"}):
        assert get_user_info_from_host_http("../etc") is None
