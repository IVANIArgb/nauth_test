from unittest.mock import MagicMock, patch

import pytest

from app import KerberosAuthenticator
from config import Settings


def test_authenticate_extracts_username_and_principal():
    settings = Settings()
    auth = KerberosAuthenticator(settings)
    mock_ctx = MagicMock()
    mock_ctx.client_principal = "alice@EXAMPLE.COM"

    with patch("app.spnego") as mock_spnego:
        mock_spnego.server.return_value = mock_ctx
        result = auth.authenticate("Negotiate dG9rZW4=")

    assert result["username"] == "alice"
    assert result["principal"] == "alice@EXAMPLE.COM"


@pytest.mark.parametrize("header", [None, "", "Basic abc"])
def test_authenticate_rejects_invalid_header(header):
    settings = Settings()
    auth = KerberosAuthenticator(settings)
    with pytest.raises(ValueError):
        auth.authenticate(header)
