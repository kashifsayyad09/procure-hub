"""The procurement hand-off across three real services: purchase request -> approval -> decision back on the request."""
import pytest

from conftest import wait_until

pytestmark = pytest.mark.e2e

PR = "/api/v1/purchase-requests"
AP = "/api/v1/approvals"


def body(total_each="25000.00", qty="2", title="Standing desks"):
    return {"title": title, "justification": "Back pain", "department": "Facilities", "priority": "high", "currency": "INR",
            "items": [{"description": "Desk", "quantity": qty, "unit": "each", "unit_price": total_each}]}


def submit(stack, who="erin@example.com", **kw) -> str:
    t = stack.tokens[who]
    r = stack.call("pr", "POST", PR, t, json=body(**kw))
    assert r.status_code == 201, r.text
    rid = r.json()["id"]
    s = stack.call("pr", "POST", f"{PR}/{rid}/submit", t)
    assert s.status_code == 200 and s.json()["status"] == "submitted", s.text
    return rid


def approval_for(stack, request_id, who="mia@example.com"):
    """Finds the approval workflow for a request (waits for the hand-off to arrive)."""
    def find():
        items = stack.call("approval", "GET", AP, stack.tokens[who], params={"view": "all", "page_size": 100}).json()["items"]
        return next((a for a in items if a["request_id"] == request_id), None)
    return wait_until(find, message="the approval to appear")


def request_status(stack, rid, who="erin@example.com"):
    return stack.call("pr", "GET", f"{PR}/{rid}", stack.tokens[who]).json()


def wait_status(stack, rid, status, who="erin@example.com"):
    return wait_until(lambda: (r := request_status(stack, rid, who))["status"] == status and r, message=f"request to become {status}")


def test_a_request_is_approved_end_to_end(stack):
    rid = submit(stack)  # 50,000 INR: one level
    ap = approval_for(stack, rid)
    assert ap["status"] == "pending" and ap["total_levels"] == 1 and ap["requester_name"] == "Erin Employee"
    assert stack.call("approval", "POST", f"{AP}/{ap['id']}/approve", stack.tokens["erin@example.com"], json={}).status_code == 403  # the requester has no approval rights
    r = stack.call("approval", "POST", f"{AP}/{ap['id']}/approve", stack.tokens["mia@example.com"], json={"comment": "Looks right"})
    assert r.status_code == 200 and r.json()["status"] == "approved"
    done = wait_status(stack, rid, "approved")
    assert done["decided_by_name"] == "Mia Manager" and done["decision_note"] == "Looks right" and done["history"][-1]["to_status"] == "approved"
    assert stack.call("pr", "PUT", f"{PR}/{rid}", stack.tokens["erin@example.com"], json=body() | {"version": done["version"]}).status_code == 409  # decided requests are locked


def test_a_large_request_needs_two_different_managers(stack):
    rid = submit(stack, total_each="80000.00")  # 160,000 INR: two levels
    ap = approval_for(stack, rid)
    assert ap["total_levels"] == 2
    ok = stack.call("approval", "POST", f"{AP}/{ap['id']}/approve", stack.tokens["mia@example.com"], json={})
    assert ok.json()["status"] == "pending" and ok.json()["current_level"] == 2
    assert request_status(stack, rid)["status"] == "submitted"  # the requester hears only the final outcome
    again = stack.call("approval", "POST", f"{AP}/{ap['id']}/approve", stack.tokens["mia@example.com"], json={})
    assert again.status_code == 403
    assert stack.call("approval", "POST", f"{AP}/{ap['id']}/approve", stack.tokens["max@example.com"], json={"comment": "Second sign-off"}).json()["status"] == "approved"
    assert wait_status(stack, rid, "approved")["decision_note"] == "Second sign-off"


def test_a_rejection_reason_reaches_the_employee(stack):
    rid = submit(stack, title="Gaming chairs")
    ap = approval_for(stack, rid)
    assert stack.call("approval", "POST", f"{AP}/{ap['id']}/reject", stack.tokens["mia@example.com"], json={"reason": "no"}).status_code == 422
    assert stack.call("approval", "POST", f"{AP}/{ap['id']}/reject", stack.tokens["mia@example.com"], json={"reason": "Over budget this quarter"}).status_code == 200
    r = wait_status(stack, rid, "rejected")
    assert r["decision_note"] == "Over budget this quarter" and r["decided_by_name"] == "Mia Manager"


def test_delegation_uses_the_real_manager_list_from_the_auth_service(stack):
    rid = submit(stack, title="Delegated purchase")
    ap = approval_for(stack, rid)
    delegates = stack.call("approval", "GET", f"{AP}/delegates", stack.tokens["mia@example.com"]).json()
    names = {d["full_name"]: d["id"] for d in delegates}
    assert {"Max Manager", "Mona Manager"} <= set(names) and "Mia Manager" not in names and "Erin Employee" not in names and "Pat Procurement" not in names
    assert stack.call("approval", "POST", f"{AP}/{ap['id']}/delegate", stack.tokens["mia@example.com"], json={"user_id": names["Max Manager"], "note": "Away"}).status_code == 200
    assert stack.call("approval", "POST", f"{AP}/{ap['id']}/approve", stack.tokens["mona@example.com"], json={}).status_code == 403
    assert stack.call("approval", "POST", f"{AP}/{ap['id']}/approve", stack.tokens["mia@example.com"], json={}).status_code == 403
    assert stack.call("approval", "POST", f"{AP}/{ap['id']}/approve", stack.tokens["max@example.com"], json={}).status_code == 200
    assert wait_status(stack, rid, "approved")["decided_by_name"] == "Max Manager"
    employee_id = stack.call("auth", "GET", "/api/v1/auth/me", stack.tokens["erin@example.com"]).json()["id"]
    other = submit(stack, title="Another")
    ap2 = approval_for(stack, other)
    assert stack.call("approval", "POST", f"{AP}/{ap2['id']}/delegate", stack.tokens["mia@example.com"], json={"user_id": employee_id}).status_code == 422  # not a manager


def test_cancelling_a_submitted_request_closes_its_approval(stack):
    rid = submit(stack, title="Changed my mind")
    ap = approval_for(stack, rid)
    assert stack.call("pr", "POST", f"{PR}/{rid}/cancel", stack.tokens["erin@example.com"], json={"reason": "Budget frozen"}).status_code == 200
    wait_until(lambda: stack.call("approval", "GET", f"{AP}/{ap['id']}", stack.tokens["mia@example.com"]).json()["status"] == "cancelled", message="the approval to be cancelled")
    assert stack.call("approval", "POST", f"{AP}/{ap['id']}/approve", stack.tokens["mia@example.com"], json={}).status_code == 409
    assert request_status(stack, rid)["status"] == "cancelled"


def test_submitting_works_while_the_approval_service_is_down_and_catches_up(stack):
    stack.stop("approval")
    try:
        rid = submit(stack, title="Submitted during an outage")  # the employee is not blocked
        assert request_status(stack, rid)["status"] == "submitted"
    finally:
        stack.start("approval")
    ap = approval_for(stack, rid)  # the retry loop in the Purchase Request service registers it
    assert ap["status"] == "pending" and ap["title"] == "Submitted during an outage"
    assert stack.call("approval", "POST", f"{AP}/{ap['id']}/approve", stack.tokens["mia@example.com"], json={}).status_code == 200
    wait_status(stack, rid, "approved")


def test_a_decision_made_while_the_request_service_is_down_is_delivered_later(stack):
    rid = submit(stack, title="Decided during an outage")
    ap = approval_for(stack, rid)
    stack.stop("pr")
    try:
        r = stack.call("approval", "POST", f"{AP}/{ap['id']}/approve", stack.tokens["max@example.com"], json={"comment": "Fine"})
        assert r.status_code == 200 and r.json()["status"] == "approved" and r.json()["decision_sync"] == "pending"
    finally:
        stack.start("pr")
    done = wait_status(stack, rid, "approved")
    assert done["decided_by_name"] == "Max Manager" and done["decision_note"] == "Fine"
    wait_until(lambda: stack.call("approval", "GET", f"{AP}/{ap['id']}", stack.tokens["mia@example.com"]).json()["decision_sync"] == "synced", message="decision to sync")


def test_access_is_enforced_across_services(stack):
    rid = submit(stack, title="Access check")
    ap = approval_for(stack, rid)
    e, p, v = stack.tokens["erin@example.com"], stack.tokens["pat@example.com"], stack.tokens["vera@example.com"]
    for token in (e, p, v):
        assert stack.call("approval", "GET", AP, token).status_code == 403
    assert stack.call("approval", "GET", AP).status_code == 401
    assert stack.call("pr", "GET", f"{PR}/{rid}", stack.tokens["emma@example.com"]).status_code == 404  # another employee
    assert stack.call("pr", "GET", f"{PR}/{rid}", stack.tokens["mia@example.com"]).status_code == 403  # managers read approvals, not requests
    assert stack.call("pr", "GET", f"{PR}/{rid}", p).status_code == 404  # procurement sees only approved requests
    stack.call("approval", "POST", f"{AP}/{ap['id']}/approve", stack.tokens["mia@example.com"], json={})
    wait_status(stack, rid, "approved")
    assert stack.call("pr", "GET", f"{PR}/{rid}", p).status_code == 200  # now visible to procurement
    assert stack.call("pr", "POST", f"{PR}/{rid}/cancel", p, json={"reason": "abc"}).status_code == 403
    admin = stack.tokens["admin"]
    for svc_name, path in (("pr", f"/internal/v1/purchase-requests/{rid}/decision"), ("approval", "/internal/v1/approvals")):
        assert stack.call(svc_name, "POST", path, admin, json={}).status_code == 401  # internal APIs refuse user tokens, even an admin's
        assert stack.call(svc_name, "POST", path, json={}).status_code == 401
    assert stack.call("auth", "GET", "/internal/v1/users", admin).status_code == 401


def test_the_manager_queue_excludes_what_a_manager_cannot_decide(stack):
    rid = submit(stack, total_each="80000.00", title="Queue check")
    ap = approval_for(stack, rid)
    queue = lambda who: {a["request_id"] for a in stack.call("approval", "GET", AP, stack.tokens[who], params={"page_size": 100}).json()["items"]}  # noqa: E731
    assert rid in queue("mia@example.com") and rid in queue("max@example.com")
    stack.call("approval", "POST", f"{AP}/{ap['id']}/approve", stack.tokens["mia@example.com"], json={})
    assert rid not in queue("mia@example.com") and rid in queue("max@example.com")  # Mia already approved level 1
    stack.call("approval", "POST", f"{AP}/{ap['id']}/approve", stack.tokens["max@example.com"], json={})
    assert rid not in queue("max@example.com") and rid not in queue("mona@example.com")


def test_dashboard_numbers_come_from_real_data(stack):
    s = stack.call("approval", "GET", f"{AP}/summary", stack.tokens["mia@example.com"]).json()
    assert s["approved_30d"] >= 3 and s["decided_by_me_30d"] >= 3 and s["approved_value_30d"].get("INR") and s["avg_decision_hours_30d"] is not None
    e = stack.call("pr", "GET", f"{PR}/summary", stack.tokens["erin@example.com"]).json()
    assert e["counts"]["approved"] >= 3 and e["counts"]["rejected"] >= 1 and e["counts"]["cancelled"] >= 1
