from datetime import date, datetime, timedelta

import pytest

from app.models import PurchaseRequest, Status
from tests.conftest import headers, payload

URL = "/api/v1/purchase-requests"


def test_submit_moves_to_submitted_and_records_history(client, create):
    r = create()
    s = client.post(f"{URL}/{r['id']}/submit", headers=headers())
    assert s.status_code == 200
    out = s.json()
    assert out["status"] == "submitted" and out["submitted_at"] and out["version"] == 2
    assert [(h["from_status"], h["to_status"]) for h in out["history"]] == [(None, "draft"), ("draft", "submitted")]


@pytest.mark.parametrize("over,message", [
    ({"items": []}, "Add at least one item"), ({"department": ""}, "Enter the department"), ({"justification": ""}, "Explain why"),
    ({"items": [{"description": "Free sample", "quantity": "1", "unit_price": "0"}]}, "greater than zero"),
])
def test_submit_rejects_incomplete_requests(client, create, over, message):
    r = create(**over)
    s = client.post(f"{URL}/{r['id']}/submit", headers=headers())
    assert s.status_code == 422 and any(message in m for m in s.json()["detail"])
    assert client.get(f"{URL}/{r['id']}", headers=headers()).json()["status"] == "draft"


def test_submit_reports_every_problem_at_once(client, create):
    r = create(items=[], department="", justification="")
    assert len(client.post(f"{URL}/{r['id']}/submit", headers=headers()).json()["detail"]) == 3


def test_submit_twice_is_a_conflict(client, create):
    r = create()
    assert client.post(f"{URL}/{r['id']}/submit", headers=headers()).status_code == 200
    assert client.post(f"{URL}/{r['id']}/submit", headers=headers()).status_code == 409


def test_submitted_request_is_locked(client, create):
    r = create()
    client.post(f"{URL}/{r['id']}/submit", headers=headers())
    assert client.put(f"{URL}/{r['id']}", headers=headers(), json=payload() | {"version": 2}).status_code == 409
    assert client.delete(f"{URL}/{r['id']}", headers=headers()).status_code == 409
    assert client.post(f"{URL}/{r['id']}/documents", headers=headers(), json={"file_name": "a.pdf", "content_type": "application/pdf", "size_bytes": 10}).status_code == 409


def test_cancel_a_submitted_request_with_a_reason(client, create):
    r = create()
    client.post(f"{URL}/{r['id']}/submit", headers=headers())
    assert client.post(f"{URL}/{r['id']}/cancel", headers=headers(), json={"reason": ""}).status_code == 422
    c = client.post(f"{URL}/{r['id']}/cancel", headers=headers(), json={"reason": "Budget frozen"})
    assert c.status_code == 200
    out = c.json()
    assert out["status"] == "cancelled" and out["cancel_reason"] == "Budget frozen" and out["history"][-1]["note"] == "Budget frozen"
    assert client.post(f"{URL}/{r['id']}/cancel", headers=headers(), json={"reason": "again"}).status_code == 409
    assert client.post(f"{URL}/{r['id']}/submit", headers=headers()).status_code == 409


def test_a_draft_is_deleted_not_cancelled(client, create):
    r = create()
    c = client.post(f"{URL}/{r['id']}/cancel", headers=headers(), json={"reason": "no longer needed"})
    assert c.status_code == 409 and "Delete a draft" in c.json()["detail"]


def test_approved_and_rejected_requests_cannot_be_cancelled_or_edited(client, create, db):
    for st in (Status.APPROVED, Status.REJECTED):
        r = create()
        row = db.get(PurchaseRequest, r["id"])
        row.status = st.value
        db.commit()
        assert client.post(f"{URL}/{r['id']}/cancel", headers=headers(), json={"reason": "change of mind"}).status_code == 409
        assert client.put(f"{URL}/{r['id']}", headers=headers(), json=payload() | {"version": 1}).status_code == 409


def test_submit_fails_if_the_needed_by_date_has_passed(client, create, db):
    r = create()
    row = db.get(PurchaseRequest, r["id"])
    row.needed_by = date.today() - timedelta(days=1)
    db.commit()
    s = client.post(f"{URL}/{r['id']}/submit", headers=headers())
    assert s.status_code == 422 and any("needed-by" in m for m in s.json()["detail"])


# ---- documents -------------------------------------------------------------------------------------
DOC = {"file_name": "quote.pdf", "content_type": "application/pdf", "size_bytes": 2048}


def test_add_and_remove_document_metadata(client, create):
    r = create()
    d = client.post(f"{URL}/{r['id']}/documents", headers=headers(), json=DOC)
    assert d.status_code == 201
    doc = d.json()
    assert doc["file_name"] == "quote.pdf" and doc["content_stored"] is False and "storage_key" not in doc
    assert len(client.get(f"{URL}/{r['id']}", headers=headers()).json()["documents"]) == 1
    assert client.delete(f"{URL}/{r['id']}/documents/{doc['id']}", headers=headers()).status_code == 204
    assert client.get(f"{URL}/{r['id']}", headers=headers()).json()["documents"] == []
    assert client.delete(f"{URL}/{r['id']}/documents/{doc['id']}", headers=headers()).status_code == 404


@pytest.mark.parametrize("over,field", [
    ({"content_type": "application/x-msdownload"}, "content_type"), ({"content_type": "text/html"}, "content_type"), ({"content_type": "image/svg+xml"}, "content_type"),
    ({"size_bytes": 0}, "size_bytes"), ({"size_bytes": 10 * 1024 * 1024 + 1}, "size_bytes"), ({"file_name": ""}, "file_name"), ({"file_name": ".."}, "file_name"),
])
def test_document_validation(client, create, over, field):
    r = create()
    resp = client.post(f"{URL}/{r['id']}/documents", headers=headers(), json=DOC | over)
    assert resp.status_code == 422 and field in str(resp.json()["detail"])


def test_document_file_names_lose_any_path(client, create):
    r = create()
    for sent, stored in [("../../etc/passwd", "passwd"), ("C:\\Users\\a\\invoice.pdf", "invoice.pdf"), ("a/b/c.pdf", "c.pdf")]:
        d = client.post(f"{URL}/{r['id']}/documents", headers=headers(), json=DOC | {"file_name": sent})
        assert d.status_code == 201 and d.json()["file_name"] == stored


def test_at_most_ten_documents(client, create):
    r = create()
    for i in range(10):
        assert client.post(f"{URL}/{r['id']}/documents", headers=headers(), json=DOC | {"file_name": f"f{i}.pdf"}).status_code == 201
    assert client.post(f"{URL}/{r['id']}/documents", headers=headers(), json=DOC).status_code == 409


def test_history_and_documents_keep_their_order_even_with_identical_timestamps(client, create, db):
    from app.models import PurchaseRequestDocument, PurchaseRequestHistory
    r = create()
    for name in ("a.pdf", "b.pdf", "c.pdf"):
        client.post(f"{URL}/{r['id']}/documents", headers=headers(), json=DOC | {"file_name": name})
    client.post(f"{URL}/{r['id']}/submit", headers=headers())
    same = datetime(2026, 1, 1, 12, 0, 0)  # MySQL DATETIME has whole-second precision, so entries can share a timestamp
    for row in [*db.query(PurchaseRequestHistory).all(), *db.query(PurchaseRequestDocument).all()]:
        row.created_at = same
    db.commit()
    out = client.get(f"{URL}/{r['id']}", headers=headers()).json()
    assert [(h["from_status"], h["to_status"]) for h in out["history"]] == [(None, "draft"), ("draft", "submitted")]
    assert [d["file_name"] for d in out["documents"]] == ["a.pdf", "b.pdf", "c.pdf"]
