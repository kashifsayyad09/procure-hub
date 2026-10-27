from datetime import date, timedelta

import pytest

from tests.conftest import headers, payload

URL = "/api/v1/purchase-requests"


def test_create_draft_computes_totals_and_numbers(client, create):
    r = create()
    assert r["status"] == "draft" and r["version"] == 1 and r["requester_name"] == "Alice Employee" and r["requester_email"] == "alice@example.com"
    assert r["number"] == f"PR-{date.today().year}-000001"
    assert [i["line_no"] for i in r["items"]] == [1, 2]
    assert r["items"][0]["line_total"] == "96000.00" and r["items"][1]["line_total"] == "3002.00"
    assert r["total_amount"] == "99002.00" and r["item_count"] == 2
    assert [h["to_status"] for h in r["history"]] == ["draft"] and r["history"][0]["actor_name"] == "Alice Employee"


def test_numbers_are_sequential_and_unique(create):
    nums = [create()["number"] for _ in range(5)]
    assert nums == [f"PR-{date.today().year}-{i:06d}" for i in range(1, 6)]


def test_money_uses_exact_decimal_arithmetic(create):
    r = create(items=[{"description": "a", "quantity": "3", "unit_price": "0.10"}, {"description": "b", "quantity": "0.333", "unit_price": "10.00"},
                      {"description": "c", "quantity": "2.5", "unit_price": "19.99"}])
    assert [i["line_total"] for i in r["items"]] == ["0.30", "3.33", "49.98"]  # 49.975 rounds half up
    assert r["total_amount"] == "53.61"


@pytest.mark.parametrize("over,field", [
    ({"title": "ab"}, "title"), ({"title": ""}, "title"), ({"currency": "XYZ"}, "currency"), ({"priority": "asap"}, "priority"),
    ({"needed_by": str(date.today() - timedelta(days=1))}, "needed_by"),
    ({"items": [{"description": "x", "quantity": "0", "unit_price": "1"}]}, "quantity"),
    ({"items": [{"description": "x", "quantity": "-1", "unit_price": "1"}]}, "quantity"),
    ({"items": [{"description": "x", "quantity": "1", "unit_price": "-5"}]}, "unit_price"),
    ({"items": [{"description": "x", "quantity": "1", "unit_price": "1.234"}]}, "unit_price"),
    ({"items": [{"description": "x", "quantity": "1", "unit_price": "1e12"}]}, "unit_price"),
    ({"items": [{"description": "   ", "quantity": "1", "unit_price": "1"}]}, "description"),
    ({"items": [{"description": "x", "quantity": "1", "unit_price": "1"}] * 101}, "items"),
    ({"justification": "x" * 2001}, "justification"),
])
def test_create_validation(client, over, field):
    r = client.post(URL, headers=headers(), json=payload(**over))
    assert r.status_code == 422, r.text
    assert field in str(r.json()["detail"])


def test_a_draft_may_be_incomplete_but_not_nameless(client):
    r = client.post(URL, headers=headers(), json={"title": "Just an idea"})
    assert r.status_code == 201 and r.json()["items"] == [] and r.json()["total_amount"] == "0.00"


def test_text_is_cleaned(client, create):
    r = create(title="  Chairs\x00\x07  ", items=[{"description": "Chair\x00", "quantity": "1", "unit_price": "1", "notes": "   "}])
    assert r["title"] == "Chairs" and r["items"][0]["description"] == "Chair" and r["items"][0]["notes"] is None


def test_markup_is_stored_as_text_not_interpreted(create):
    r = create(title="<img src=x onerror=alert(1)>")
    assert r["title"] == "<img src=x onerror=alert(1)>"  # the React UI renders text, never HTML


def test_update_draft_replaces_items_and_bumps_version(client, create):
    r = create()
    body = payload(title="Laptops and docks", items=[{"description": "Dock", "quantity": "2", "unit_price": "100"}]) | {"version": r["version"]}
    u = client.put(f"{URL}/{r['id']}", headers=headers(), json=body)
    assert u.status_code == 200
    out = u.json()
    assert out["title"] == "Laptops and docks" and out["version"] == 2 and out["total_amount"] == "200.00" and len(out["items"]) == 1


def test_update_with_stale_version_is_rejected(client, create):
    r = create()
    ok = client.put(f"{URL}/{r['id']}", headers=headers(), json=payload() | {"version": 1})
    assert ok.status_code == 200
    stale = client.put(f"{URL}/{r['id']}", headers=headers(), json=payload(title="Other change") | {"version": 1})
    assert stale.status_code == 409 and "changed somewhere else" in stale.json()["detail"]
    assert client.get(f"{URL}/{r['id']}", headers=headers()).json()["title"] == "Laptops for the design team"


def test_update_requires_version(client, create):
    r = create()
    assert client.put(f"{URL}/{r['id']}", headers=headers(), json=payload()).status_code == 422


def test_delete_draft(client, create):
    r = create()
    assert client.delete(f"{URL}/{r['id']}", headers=headers()).status_code == 204
    assert client.get(f"{URL}/{r['id']}", headers=headers()).status_code == 404
    assert client.get(URL, headers=headers()).json()["total"] == 0


def test_unknown_id_is_404(client):
    for call in (lambda: client.get(f"{URL}/nope", headers=headers()), lambda: client.delete(f"{URL}/nope", headers=headers()),
                 lambda: client.post(f"{URL}/nope/submit", headers=headers()), lambda: client.put(f"{URL}/nope", headers=headers(), json=payload() | {"version": 1})):
        assert call().status_code == 404


def test_sql_injection_strings_are_inert(client, create):
    create()
    r = client.get(URL, headers=headers(), params={"q": "' OR 1=1 --"})
    assert r.status_code == 200 and r.json()["total"] == 0
    assert client.get(f"{URL}/' OR '1'='1", headers=headers()).status_code == 404
    assert client.get(URL, headers=headers()).json()["total"] == 1
