"""AD profile cache from Windows host."""
import json
import os

import pytest

from auth.ad_host_cache import get_user_info_from_host_cache


@pytest.fixture
def cache_dir(tmp_path, monkeypatch):
    d = tmp_path / "ad-cache"
    d.mkdir()
    monkeypatch.setenv("AD_HOST_PROFILE_CACHE_ENABLED", "true")
    monkeypatch.setenv("AD_HOST_PROFILE_CACHE_DIR", str(d))
    return d


def test_reads_host_cache(cache_dir):
    path = cache_dir / "ivanov.json"
    path.write_text(
        json.dumps(
            {
                "first_name": "Ivan",
                "second_name": "Ivanovich",
                "sur_name": "Ivanov",
                "department": "IT",
                "position": "Engineer",
            }
        ),
        encoding="utf-8",
    )
    info = get_user_info_from_host_cache("ivanov")
    assert info["sur_name"] == "Ivanov"
    assert info["department"] == "IT"


def test_missing_cache_returns_none(cache_dir):
    assert get_user_info_from_host_cache("nobody") is None
