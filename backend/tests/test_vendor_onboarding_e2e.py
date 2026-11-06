"""Vendor onboarding across real services: tokens issued by the real auth service are accepted by the real vendor service,
and the role rules hold end to end."""
import pytest

pytestmark = pytest.mark.e2e

VN = "/api/v1/vendors"


def profile(**over):
    base = {"legal_name": "Acme Supplies Private Limited", "tax_id": "29ABCDE1234F1Z5", "address_line1": "12 Industrial Layout", "city": "Bengaluru", "state": "Karnataka",
            "postal_code": "560058", "country": "IN", "categories": ["it_hardware"], "payment_terms_days": 30, "currency": "INR",
            "contacts": [{"name": "Vera Vendor", "email": "vera@example.com"}]}
    base.update(over)
    return base


def test_a_vendor_registers_and_procurement_verifies_end_to_end(stack):
    vera, pat, paul = (stack.tokens[e] for e in ("vera@example.com", "pat@example.com", "paul@example.com"))
    assert stack.call("vendor", "GET", f"{VN}/me", vera).status_code == 404  # nothing registered yet
    created = stack.call("vendor", "POST", VN, vera, json=profile())
    assert created.status_code == 201, created.text
    v = created.json()
    assert v["status"] == "draft" and v["has_account"] is True
    assert stack.call("vendor", "GET", f"{VN}/me", vera).json()["id"] == v["id"]

    sub = stack.call("vendor", "POST", f"{VN}/{v['id']}/submit", vera)
    assert sub.status_code == 200 and sub.json()["status"] == "pending"
    queue = stack.call("vendor", "GET", VN, pat, params={"status": "pending"}).json()
    assert [x["id"] for x in queue["items"]] == [v["id"]]

    assert stack.call("vendor", "POST", f"{VN}/{v['id']}/verify", vera, json={"version": sub.json()["version"]}).status_code == 403  # a vendor cannot verify themselves
    done = stack.call("vendor", "POST", f"{VN}/{v['id']}/verify", paul, json={"version": sub.json()["version"], "note": "Checked"})
    assert done.status_code == 200 and done.json()["status"] == "verified" and done.json()["verified_by_name"] == "Paul Procurement"
    assert stack.call("vendor", "GET", f"{VN}/me", vera).json()["status"] == "verified"
    summary = stack.call("vendor", "GET", f"{VN}/summary", pat).json()
    assert summary["counts"]["verified"] >= 1


def test_vendors_are_isolated_from_each_other_and_from_the_directory(stack):
    victor, vera = stack.tokens["victor@example.com"], stack.tokens["vera@example.com"]
    mine = stack.call("vendor", "POST", VN, victor, json=profile(legal_name="Victor Traders", tax_id="VICTOR12345", contacts=[{"name": "Victor", "email": "victor@example.com"}]))
    assert mine.status_code == 201, mine.text
    theirs = stack.call("vendor", "GET", f"{VN}/me", vera).json()
    assert stack.call("vendor", "GET", f"{VN}/{mine.json()['id']}", vera).status_code == 404
    assert stack.call("vendor", "PUT", f"{VN}/{theirs['id']}", victor, json=profile(city="Hacked") | {"version": theirs["version"]}).status_code == 404
    assert stack.call("vendor", "GET", VN, victor).status_code == 403  # the directory is for staff
    for who in ("erin@example.com", "mia@example.com"):
        assert stack.call("vendor", "GET", VN, stack.tokens[who]).status_code == 403
        assert stack.call("vendor", "POST", VN, stack.tokens[who], json=profile(tax_id="EMPLOYEE123")).status_code == 403


def test_staff_onboard_a_vendor_and_a_second_reviewer_verifies_it(stack):
    pat, admin = stack.tokens["pat@example.com"], stack.tokens["admin"]
    walkin = profile(legal_name="Walk-in Supplies", tax_id="WALKIN99999", contacts=[{"name": "Wally", "email": "wally@walkin.example"}])
    made = stack.call("vendor", "POST", f"{VN}/onboard", pat, json=walkin)
    assert made.status_code == 201 and made.json()["has_account"] is False
    v = made.json()
    sub = stack.call("vendor", "POST", f"{VN}/{v['id']}/submit", pat).json()
    assert stack.call("vendor", "POST", f"{VN}/{v['id']}/verify", pat, json={"version": sub["version"]}).status_code == 403  # not your own submission
    assert stack.call("vendor", "POST", f"{VN}/{v['id']}/verify", admin, json={"version": sub["version"]}).json()["status"] == "verified"


def test_other_services_can_look_up_vendor_status_with_a_service_token(stack):
    """Phase 6 will use this to refuse RFQ invitations to vendors that are not verified."""
    import httpx
    from procurehub_common.service_auth import create_service_token

    pat = stack.tokens["pat@example.com"]
    ids = [x["id"] for x in stack.call("vendor", "GET", VN, pat, params={"page_size": 100}).json()["items"]]
    token = create_service_token(stack.base_env["INTERNAL_JWT_SECRET"], "quotation-service")
    r = httpx.post(stack.url("vendor") + "/internal/v1/vendors/lookup", headers={"Authorization": f"Bearer {token}"}, json={"ids": ids}, timeout=10)
    assert r.status_code == 200 and {x["id"] for x in r.json()} == set(ids)
    assert any(x["status"] == "verified" for x in r.json())
    assert stack.call("vendor", "POST", "/internal/v1/vendors/lookup", pat, json={"ids": ids}).status_code == 401  # a user token cannot use the internal API
