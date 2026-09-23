"""API sign-in: open locally, closed on Vercel without a Firebase project, and otherwise only for verified Google
accounts on the allowed list."""
import pytest
from fastapi import HTTPException

import app as web


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    for name in ("FIREBASE_PROJECT_ID", "VERCEL", "ALLOWED_EMAILS"):
        monkeypatch.delenv(name, raising=False)


def claims(**kw):
    return dict({"iss": "https://securetoken.google.com/demo", "email": "Pilot@Example.com", "email_verified": True},
                **kw)


def status(authorization=""):
    try:
        web.signed_in(authorization)
    except HTTPException as e:
        return e.status_code
    return 200


def test_open_locally_and_closed_on_vercel_without_a_project(monkeypatch):
    assert web.signed_in("") is None
    monkeypatch.setenv("VERCEL", "1")
    assert status() == 503


@pytest.mark.parametrize("header, verified, code", [
    ("", None, 401),                                                              # no token
    ("Bearer x", ValueError("Token expired"), 401),                               # bad or expired token
    ("Bearer x", claims(iss="https://securetoken.google.com/other"), 401),        # another project's token
    ("Bearer x", claims(email_verified=False), 403),
    ("Bearer x", claims(email="someone@else.com"), 403),                          # not on the list
    ("Bearer x", claims(), 200),                                                  # listed, any letter case
])
def test_signed_in(monkeypatch, header, verified, code):
    monkeypatch.setenv("FIREBASE_PROJECT_ID", "demo")
    monkeypatch.setenv("ALLOWED_EMAILS", "pilot@example.com, judge@example.com")

    def verify(token, request, audience):
        assert (token, audience) == ("x", "demo")
        if isinstance(verified, Exception):
            raise verified
        return verified

    monkeypatch.setattr(web.id_token, "verify_firebase_token", verify)
    assert status(header) == code
