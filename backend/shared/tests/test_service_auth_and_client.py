import json
from datetime import UTC, datetime, timedelta

import httpx
import jwt
import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError

from procurehub_common.contracts.approval import ApprovalRegistration, DecisionNotice
from procurehub_common.fastapi_support import service_caller
from procurehub_common.logging import request_id_var
from procurehub_common.service_auth import INTERNAL_AUDIENCE, create_service_token, verify_service_token
from procurehub_common.service_client import ServiceClient, ServiceRejected, ServiceUnavailable

SECRET = "s" * 40


def _claims(**over):
    now = datetime.now(UTC)
    base = {"iss": "approval-service", "sub": "approval-service", "aud": INTERNAL_AUDIENCE, "typ": "service", "iat": now, "exp": now + timedelta(seconds=60)}
    return base | over


def test_service_token_roundtrip():
    assert verify_service_token(create_service_token(SECRET, "approval-service"), SECRET, {"approval-service"}) == "approval-service"


@pytest.mark.parametrize("make", [
    lambda: create_service_token("x" * 40, "approval-service"),                                   # wrong secret
    lambda: jwt.encode(_claims(aud="procurehub"), SECRET, algorithm="HS256"),                      # a user-token audience
    lambda: jwt.encode(_claims(typ="access"), SECRET, algorithm="HS256"),                          # a user-token type
    lambda: jwt.encode(_claims(sub="other-service", iss="other-service"), SECRET, algorithm="HS256"),  # service not allowed
    lambda: jwt.encode(_claims(iss="someone-else"), SECRET, algorithm="HS256"),                   # issuer must equal subject
    lambda: create_service_token(SECRET, "approval-service", ttl_seconds=-5),                     # expired
    lambda: jwt.encode(_claims(), None, algorithm="none"),                                         # unsigned
    lambda: jwt.encode(_claims(), SECRET, algorithm="HS512"),                                      # other algorithm
    lambda: "garbage",
])
def test_invalid_service_tokens_are_refused(make):
    with pytest.raises(jwt.PyJWTError):
        verify_service_token(make(), SECRET, {"approval-service"})


def _client(handler, **kw):
    return ServiceClient("http://svc.local", SECRET, "approval-service", transport=httpx.MockTransport(handler), **kw)


def test_client_sends_a_verifiable_service_token_and_the_request_id():
    seen = {}

    def handler(req: httpx.Request) -> httpx.Response:
        seen["auth"], seen["rid"], seen["body"] = req.headers["authorization"], req.headers["x-request-id"], json.loads(req.content)
        return httpx.Response(200, json={"ok": True})

    token = request_id_var.set("trace-42")
    try:
        assert _client(handler).post("/internal/v1/x", json={"a": 1}) == {"ok": True}
    finally:
        request_id_var.reset(token)
    assert verify_service_token(seen["auth"].split()[1], SECRET, {"approval-service"}) == "approval-service"
    assert seen["rid"] == "trace-42" and seen["body"] == {"a": 1}


def test_client_maps_responses_to_clear_errors():
    assert _client(lambda r: httpx.Response(204)).post("/x") is None
    with pytest.raises(ServiceRejected) as e:
        _client(lambda r: httpx.Response(409, json={"detail": "Request is cancelled"})).post("/x")
    assert e.value.status_code == 409 and e.value.detail == "Request is cancelled"
    with pytest.raises(ServiceUnavailable):
        _client(lambda r: httpx.Response(503, json={})).post("/x")
    with pytest.raises(ServiceUnavailable):
        _client(lambda r: httpx.Response(500, text="boom")).get("/x")


def test_client_retries_network_errors_once_then_reports_unavailable():
    calls = []

    def boom(req):
        calls.append(1)
        raise httpx.ConnectError("refused")

    with pytest.raises(ServiceUnavailable):
        _client(boom).post("/x")
    assert len(calls) == 2


def test_client_recovers_when_the_second_attempt_works():
    calls = []

    def flaky(req):
        calls.append(1)
        if len(calls) == 1:
            raise httpx.ConnectError("refused")
        return httpx.Response(200, json={"n": 2})

    assert _client(flaky).get("/x") == {"n": 2}


def test_service_caller_dependency():
    app = FastAPI()
    secret = {"value": SECRET}

    @app.get("/internal/ping")
    def ping(caller: str = Depends(service_caller(lambda r: secret["value"], {"approval-service"}))):
        return {"caller": caller}

    c = TestClient(app)
    assert c.get("/internal/ping").status_code == 401
    assert c.get("/internal/ping", headers={"Authorization": "Bearer nope"}).status_code == 401
    user_like = jwt.encode(_claims(aud="procurehub", typ="access"), SECRET, algorithm="HS256")
    assert c.get("/internal/ping", headers={"Authorization": f"Bearer {user_like}"}).status_code == 401
    other = create_service_token(SECRET, "purchase-request-service")
    assert c.get("/internal/ping", headers={"Authorization": f"Bearer {other}"}).status_code == 401
    good = create_service_token(SECRET, "approval-service")
    assert c.get("/internal/ping", headers={"Authorization": f"Bearer {good}"}).json() == {"caller": "approval-service"}
    secret["value"] = None
    assert c.get("/internal/ping", headers={"Authorization": f"Bearer {good}"}).status_code == 503


def test_contracts_validate_their_inputs():
    base = {"request_id": "r1", "request_number": "PR-2026-000001", "title": "t", "justification": "j", "department": "d", "priority": "normal",
            "currency": "INR", "total_amount": "10.00", "requester_id": "u1", "requester_name": "A", "requester_email": "a@example.com"}
    assert ApprovalRegistration(**base).contract_version == 1
    for bad in ({"currency": "JPY"}, {"priority": "asap"}, {"title": "x" * 151}, {"total_amount": "abc"}, {"request_id": ""}, {"requester_id": ""}, {"title": ""}):
        with pytest.raises(ValidationError):
            ApprovalRegistration(**(base | bad))
    with pytest.raises(ValidationError):
        DecisionNotice(decision="maybe", actor_id="u", actor_name="A", decided_at=datetime.now())
