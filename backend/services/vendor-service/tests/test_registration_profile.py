import json

import pytest

from app.models import Vendor, VendorEvent
from tests.conftest import ADMIN, PROC, URL, VENDOR_A, VENDOR_B, headers, payload


def test_vendor_registers_their_company_as_a_draft(client, register):
    v = register()
    assert v["status"] == "draft" and v["has_account"] is True
    assert v["number"].startswith("VND-") and len(v["number"].split("-")[-1]) == 6
    assert v["legal_name"] == "Acme Supplies Private Limited" and v["tax_id"] == "29ABCDE1234F1Z5"
    assert v["categories"] == ["it_hardware", "office_supplies"]
    assert v["primary_contact_email"] == "vera@acme.example"
    assert v["completeness"] == {"percent": 100, "missing": []}
    assert [h["action"] for h in v["history"]] == ["created"] and v["history"][0]["actor_name"] == "Vera Vendor"


def test_the_owner_comes_from_the_token_never_from_the_body(client):
    r = client.post(URL, headers=VENDOR_A, json=payload() | {"owner_id": "ven-b", "status": "verified", "version": 99, "number": "VND-1"})
    assert r.status_code == 201
    body = r.json()
    assert body["status"] == "draft" and body["version"] == 1 and body["number"] != "VND-1"
    assert client.get(f"{URL}/me", headers=VENDOR_A).json()["id"] == body["id"]
    assert client.get(f"{URL}/me", headers=VENDOR_B).status_code == 404


def test_numbers_are_sequential_and_unique(register):
    a = register(VENDOR_A, tax_id="TAXAAAAA1")
    b = register(VENDOR_B, tax_id="TAXBBBBB1")
    assert int(b["number"].split("-")[-1]) == int(a["number"].split("-")[-1]) + 1


def test_a_vendor_user_can_register_only_once(client, register):
    register()
    r = client.post(URL, headers=VENDOR_A, json=payload(tax_id="OTHERTAX99"))
    assert r.status_code == 409 and "already have" in r.json()["detail"]


def test_me_is_404_until_registered(client):
    r = client.get(f"{URL}/me", headers=VENDOR_A)
    assert r.status_code == 404 and "not registered" in r.json()["detail"]


def test_staff_can_register_a_vendor_that_has_no_account(client, onboard):
    v = onboard()
    assert v["has_account"] is False and v["status"] == "draft"
    assert v["history"][0]["note"] == "Registered by staff"
    assert client.get(f"{URL}/{v['id']}", headers=VENDOR_A).status_code == 404  # nobody owns it, so no vendor user can open it


def test_the_same_tax_id_cannot_be_registered_twice_however_it_is_typed(client, register):
    register()
    for typed in ("29abcde1234f1z5", "29-ABCDE 1234 F1Z5"):
        r = client.post(f"{URL}/onboard", headers=PROC, json=payload(tax_id=typed, contacts=[]))
        assert r.status_code == 409 and "tax ID" in r.json()["detail"], typed
    assert client.post(f"{URL}/onboard", headers=PROC, json=payload(tax_id="DIFFERENT123")).status_code == 201


def test_two_drafts_without_a_tax_id_are_allowed(client):
    assert client.post(f"{URL}/onboard", headers=PROC, json=payload(tax_id=None)).status_code == 201
    assert client.post(f"{URL}/onboard", headers=PROC, json=payload(tax_id="", legal_name="Other Ltd")).status_code == 201


def test_a_draft_can_be_saved_with_only_a_name(client):
    r = client.post(URL, headers=VENDOR_A, json={"legal_name": "Tiny Traders"})
    assert r.status_code == 201
    c = r.json()["completeness"]
    assert c["percent"] < 100 and "Tax ID" in c["missing"] and "At least one category" in c["missing"]


@pytest.mark.parametrize("field,value", [
    ("legal_name", "A"), ("legal_name", " "), ("legal_name", "x" * 201), ("tax_id", "ab"), ("tax_id", "x" * 31), ("tax_id", "--- ---"),
    ("website", "acme.example"), ("website", "javascript:alert(1)"), ("website", "ftp://acme.example"), ("country", "India"), ("country", "1N"),
    ("payment_terms_days", -1), ("payment_terms_days", 366), ("currency", "JPY"), ("categories", ["weapons"]), ("categories", ["software"] * 11),
    ("description", "x" * 2001), ("postal_code", "x" * 21),
])
def test_invalid_profile_fields_are_rejected(client, field, value):
    r = client.post(URL, headers=VENDOR_A, json=payload(**{field: value}))
    assert r.status_code == 422, (field, value, r.text)


@pytest.mark.parametrize("contact", [
    {"name": "A", "email": "not-an-email"}, {"name": "A", "email": "a@b"}, {"name": "A", "email": "a b@c.com"}, {"name": "", "email": "a@b.com"},
    {"name": "A", "email": "a@b.com", "phone": "abc"}, {"name": "A", "email": "a@b.com", "phone": "12"},
])
def test_invalid_contacts_are_rejected(client, contact):
    assert client.post(URL, headers=VENDOR_A, json=payload(contacts=[contact])).status_code == 422


def test_contact_rules(client):
    two_primary = [{"name": "A", "email": "a@x.com", "is_primary": True}, {"name": "B", "email": "b@x.com", "is_primary": True}]
    assert client.post(URL, headers=VENDOR_A, json=payload(contacts=two_primary)).status_code == 422
    same_email = [{"name": "A", "email": "a@x.com"}, {"name": "B", "email": "A@X.com"}]
    assert client.post(URL, headers=VENDOR_A, json=payload(contacts=same_email)).status_code == 422
    assert client.post(URL, headers=VENDOR_A, json=payload(contacts=[{"name": "A", "email": "a@x.com"}] * 1 + [{"name": f"P{i}", "email": f"p{i}@x.com"} for i in range(10)])).status_code == 422


def test_the_first_contact_is_primary_when_none_is_chosen(client):
    r = client.post(URL, headers=VENDOR_A, json=payload(contacts=[{"name": "Zed", "email": "ZED@Acme.example"}, {"name": "Amy", "email": "amy@acme.example"}]))
    assert r.status_code == 201
    contacts = r.json()["contacts"]
    assert [c["is_primary"] for c in contacts] == [True, False] and contacts[0]["email"] == "zed@acme.example"  # emails are lower-cased


def test_text_is_cleaned_and_categories_deduplicated(client):
    r = client.post(URL, headers=VENDOR_A, json=payload(legal_name="  Acme\x00 Ltd  ", city=" Pune\x07 ", categories=["software", "software", "furniture"], trade_name="   "))
    assert r.status_code == 201
    b = r.json()
    assert b["legal_name"] == "Acme Ltd" and b["city"] == "Pune" and b["categories"] == ["software", "furniture"] and b["trade_name"] is None


def test_update_replaces_the_profile_and_bumps_the_version(client, register):
    v = register()
    r = client.put(f"{URL}/{v['id']}", headers=VENDOR_A, json=payload(city="Mysuru", categories=["furniture"], contacts=[{"name": "New Person", "email": "new@acme.example"}]) | {"version": v["version"]})
    assert r.status_code == 200, r.text
    b = r.json()
    assert b["city"] == "Mysuru" and b["categories"] == ["furniture"] and [c["name"] for c in b["contacts"]] == ["New Person"]
    assert b["version"] == v["version"] + 1 and b["status"] == "draft"
    assert [h["action"] for h in b["history"]] == ["created", "updated"]


def test_a_stale_version_is_refused(client, register):
    v = register()
    ok = client.put(f"{URL}/{v['id']}", headers=VENDOR_A, json=payload(city="A") | {"version": 1})
    assert ok.status_code == 200
    stale = client.put(f"{URL}/{v['id']}", headers=VENDOR_A, json=payload(city="B") | {"version": 1})
    assert stale.status_code == 409 and "changed somewhere else" in stale.json()["detail"]
    assert client.get(f"{URL}/{v['id']}", headers=VENDOR_A).json()["city"] == "A"


def test_updating_to_another_vendors_tax_id_is_refused(client, register):
    register(VENDOR_A)
    b = register(VENDOR_B, tax_id="BBBBB22222")
    r = client.put(f"{URL}/{b['id']}", headers=VENDOR_B, json=payload(tax_id="29abcde1234f1z5") | {"version": b["version"]})
    assert r.status_code == 409


def test_keeping_your_own_tax_id_on_update_is_fine(client, register):
    v = register()
    assert client.put(f"{URL}/{v['id']}", headers=VENDOR_A, json=payload(description="Changed") | {"version": 1}).status_code == 200


def test_a_vendor_cannot_read_or_change_another_vendors_record(client, register):
    a = register(VENDOR_A)
    assert client.get(f"{URL}/{a['id']}", headers=VENDOR_B).status_code == 404
    assert client.put(f"{URL}/{a['id']}", headers=VENDOR_B, json=payload() | {"version": 1}).status_code == 404
    assert client.post(f"{URL}/{a['id']}/submit", headers=VENDOR_B).status_code == 404
    assert client.get(f"{URL}/{a['id']}", headers=VENDOR_A).status_code == 200


def test_unknown_vendor_is_404_for_everyone(client):
    for h in (VENDOR_A, PROC, ADMIN):
        assert client.get(f"{URL}/nope", headers=h).status_code == 404


def test_staff_can_edit_any_vendor_and_the_edit_is_recorded(client, register):
    v = register()
    r = client.put(f"{URL}/{v['id']}", headers=PROC, json=payload(payment_terms_days=45) | {"version": 1})
    assert r.status_code == 200 and r.json()["payment_terms_days"] == 45
    assert r.json()["history"][-1]["actor_name"] == "Pat Procurement"


def test_changes_write_outbox_events_in_the_same_transaction(client, db, register):
    v = register()
    client.put(f"{URL}/{v['id']}", headers=VENDOR_A, json=payload(city="X") | {"version": 1})
    events = db.query(VendorEvent).order_by(VendorEvent.created_at).all()
    assert sorted(e.type for e in events) == ["vendor_registered", "vendor_updated"]
    body = json.loads(events[0].payload)
    assert body["vendor_id"] == v["id"] and body["number"] == v["number"] and all(e.published_at is None for e in events)


def test_a_failed_registration_leaves_no_partial_record(client, db):
    client.post(URL, headers=VENDOR_A, json=payload(categories=["nope"]))
    assert db.query(Vendor).count() == 0 and db.query(VendorEvent).count() == 0


def test_responses_never_include_the_owner_id_or_internal_fields(client, register):
    v = register()
    text = client.get(f"{URL}/{v['id']}", headers=PROC).text
    assert "owner_id" not in text and "submitted_by_id" not in text and "ven-a" not in text


def test_unknown_fields_in_the_body_are_ignored_not_stored(client, db, register):
    register(**{"verified_by_name": "Mallory"})
    assert db.query(Vendor).one().verified_by_name is None


@pytest.mark.parametrize("h", [headers("employee"), headers("manager"), headers("finance")])
def test_roles_with_no_vendor_permissions_cannot_register(client, h):
    assert client.post(URL, headers=h, json=payload()).status_code == 403
    assert client.post(f"{URL}/onboard", headers=h, json=payload()).status_code == 403


def test_the_unique_indexes_catch_two_requests_that_race_past_the_checks(client, monkeypatch, register):
    """Both checks pass for both requests when they run at the same moment; the database must still refuse the second."""
    from app import service
    register()
    monkeypatch.setattr(service, "_tax_id_free", lambda *a, **k: None)
    same_tax = client.post(f"{URL}/onboard", headers=PROC, json=payload())
    assert same_tax.status_code == 409 and "tax ID" in same_tax.json()["detail"]
    same_owner = client.post(URL, headers=VENDOR_A, json=payload(tax_id="RACE000001"))
    assert same_owner.status_code == 409
    assert client.get(URL, headers=PROC).json()["total"] == 1  # nothing half-saved
