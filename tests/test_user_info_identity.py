"""Identity fields on /user/info-test must not keep EXAMPLE.COM when domain is real."""


def test_finalize_identity_from_domain():
    from auth.new_auth import NewAuth

    payload = {
        "username": "ivanov",
        "domain": "GIPROTNG",
        "realm": "EXAMPLE.COM",
        "principal": "ivanov@EXAMPLE.COM",
        "email": "ivanov@company.com",
    }
    NewAuth.finalize_user_identity_payload(payload, "ivanov")
    assert payload["realm"] == "GIPROTNG"
    assert payload["principal"] == "ivanov@GIPROTNG"
    assert payload["email"] == "ivanov@giprotng"
