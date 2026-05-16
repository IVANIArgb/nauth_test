from unittest.mock import MagicMock, patch

from app import ADClient
from config import Settings


def test_ldap_fetch_user_success():
    settings = Settings()
    client = ADClient(settings)

    fake_entry = MagicMock()
    fake_entry.sAMAccountName.value = "alice"
    fake_entry.displayName.value = "Alice Smith"
    fake_entry.mail.value = "alice@example.com"
    fake_entry.department.value = "IT"
    fake_entry.title.value = "Engineer"

    fake_conn = MagicMock()
    fake_conn.entries = [fake_entry]
    fake_conn.search.return_value = True

    with patch("app.Connection", return_value=fake_conn), patch("app.Server"):
        data = client.fetch_user("alice")

    assert data["sAMAccountName"] == "alice"
    assert data["department"] == "IT"
