import time
from datetime import UTC, datetime, timedelta

import jwt
import pytest

from app.config import Settings
from app.models import Role, User
from app.permissions import PERMISSIONS, permissions_for
from app.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    hash_refresh_token,
    needs_rehash,
    new_refresh_token,
    password_policy_errors,
    verify_password,
)


def _user():
    return User(id="u-1", email="a@example.com", full_name="A", role="manager", password_hash="x")


def test_password_hash_roundtrip_and_salting():
    h1, h2 = hash_password("Correct-horse-42"), hash_password("Correct-horse-42")
    assert h1 != h2 and h1.startswith("$argon2id$")
    assert verify_password("Correct-horse-42", h1)
    assert not verify_password("wrong", h1)
    assert not verify_password("x", "not-a-hash")
    assert not needs_rehash(h1)


@pytest.mark.parametrize("pw,ok", [("short1", False), ("alllettersonlylong", False), ("123456789012", False), ("Correct-horse-42", True), ("x" * 129 + "1", False)])
def test_password_policy(pw, ok):
    assert (password_policy_errors(pw) == []) is ok


def test_password_policy_rejects_email_name():
    assert password_policy_errors("jonathan-Password1", "jonathan@example.com")


def test_access_token_roundtrip(settings):
    token, ttl = create_access_token(settings, _user())
    claims = decode_access_token(settings, token)
    assert (claims["sub"], claims["role"], claims["typ"]) == ("u-1", "manager", "access") and ttl == 900


def test_expired_token_rejected(settings):
    s = Settings(database_url="sqlite://", jwt_secret="x" * 40, access_token_ttl_minutes=-1)
    token, _ = create_access_token(s, _user())
    with pytest.raises(jwt.ExpiredSignatureError):
        decode_access_token(settings, token)


def test_wrong_secret_audience_issuer_and_type_rejected(settings):
    other = Settings(database_url="sqlite://", jwt_secret="y" * 40)
    with pytest.raises(jwt.InvalidSignatureError):
        decode_access_token(settings, create_access_token(other, _user())[0])
    for override in ({"jwt_audience": "other"}, {"jwt_issuer": "other"}):
        s = Settings(database_url="sqlite://", jwt_secret="x" * 40, **override)
        with pytest.raises(jwt.InvalidTokenError):
            decode_access_token(settings, create_access_token(s, _user())[0])
    now = datetime.now(UTC)
    refresh_like = jwt.encode({"iss": settings.jwt_issuer, "aud": settings.jwt_audience, "sub": "u", "iat": now, "exp": now + timedelta(minutes=5), "typ": "refresh"}, "x" * 40, algorithm="HS256")
    with pytest.raises(jwt.InvalidTokenError):
        decode_access_token(settings, refresh_like)


def test_alg_none_and_other_algorithms_rejected(settings):
    now = int(time.time())
    claims = {"iss": settings.jwt_issuer, "aud": settings.jwt_audience, "sub": "u", "iat": now, "exp": now + 300, "typ": "access"}
    with pytest.raises(jwt.PyJWTError):
        decode_access_token(settings, jwt.encode(claims, None, algorithm="none"))
    with pytest.raises(jwt.PyJWTError):
        decode_access_token(settings, jwt.encode(claims, "x" * 40, algorithm="HS512"))


def test_short_jwt_secret_refused():
    with pytest.raises(ValueError):
        Settings(database_url="sqlite://", jwt_secret="short")


def test_refresh_tokens_are_random_and_hashed():
    a, ha = new_refresh_token()
    b, _ = new_refresh_token()
    assert a != b and len(a) >= 60 and ha == hash_refresh_token(a) and a not in ha


def test_permission_matrix_separation_of_duties():
    assert all(PERMISSIONS[r] for r in Role)
    holders = {p: [r for r in Role if p in PERMISSIONS[r]] for p in {p for s in PERMISSIONS.values() for p in s}}
    assert holders["user:manage"] == [Role.ADMIN] and holders["role:assign"] == [Role.ADMIN]
    assert holders["approval:decide"] == [Role.MANAGER]
    assert "purchase_order:create" not in PERMISSIONS[Role.EMPLOYEE] | PERMISSIONS[Role.VENDOR]
    assert permissions_for("nonsense") == []
