"""Comparison, supplier evaluation and selection. Money is exact decimals; all totals and scores are computed here, never in the browser."""
import json
from decimal import Decimal

from procurehub_common.contracts.quotation import AwardItem, AwardRef
from procurehub_common.tokens import TokenClaims
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .common import Clients, commit, err, event, log_history, quotations_open, vendor_lookup
from .models import Evaluation, Quotation, QuotationStatus, Rfq, RfqStatus, Selection, SelectionStatus, utcnow
from .schemas import EvaluationIn, SelectIn
from .scoring import WEIGHTS, Candidate, Scored, score
from .service import LIVE_QUOTATION, active_selection, get_rfq, is_complete, missing_lines


def _open_quotations(db: Session, rfq: Rfq) -> list[Quotation]:
    rows = db.scalars(select(Quotation).where(Quotation.rfq_id == rfq.id, Quotation.status.in_(LIVE_QUOTATION)).order_by(Quotation.submitted_at, Quotation.id)).all()
    return list(rows)


def require_open(rfq: Rfq) -> None:
    if not quotations_open(rfq, utcnow()):
        if rfq.status == RfqStatus.CANCELLED.value:
            raise err(409, "This RFQ was cancelled.")
        raise err(409, "Quotations stay sealed until the deadline passes or the RFQ is closed.")


def _candidates(quotes: list[Quotation], evals: dict[str, Evaluation]) -> list[Candidate]:
    out = []
    for n, q in enumerate(quotes):
        ev = evals.get(q.id)
        out.append(Candidate(key=q.id, currency=q.currency, total=q.total_amount, lead_time_days=q.lead_time_days, complete=is_complete(q),
                             compliance_score=ev.compliance_score if ev else None, terms_score=ev.terms_score if ev else None, submitted_order=n))
    return out


def _evals(db: Session, rfq: Rfq) -> dict[str, Evaluation]:
    return {e.quotation_id: e for e in db.scalars(select(Evaluation).where(Evaluation.rfq_id == rfq.id))}


def _scores_dict(s: Scored) -> dict:
    return {"price": s.price, "delivery": s.delivery, "compliance": s.compliance, "terms": s.terms, "total": s.total, "missing": s.missing}


def compare(db: Session, rfq_id: str, clients: Clients) -> dict:
    rfq = get_rfq(db, rfq_id)
    require_open(rfq)
    quotes = _open_quotations(db, rfq)
    evals = _evals(db, rfq)
    scored = score(_candidates(quotes, evals))
    vendors: dict[str, dict] = {}
    info = True
    if quotes:
        try:
            vendors = vendor_lookup(clients, list({q.vendor_id for q in quotes}))
        except Exception:  # noqa: BLE001 - the comparison still works without live vendor information; selection will not
            info = False
    rows = []
    for q in quotes:
        s = scored[q.id]
        ev = evals.get(q.id)
        complete = is_complete(q)
        rows.append({
            "id": q.id, "number": q.number, "vendor_id": q.vendor_id, "vendor_number": q.vendor_number, "vendor_name": q.vendor_name,
            "vendor_status": vendors.get(q.vendor_id, {}).get("status") if info else None, "currency": q.currency, "status": q.status, "total_amount": q.total_amount,
            "lead_time_days": q.lead_time_days, "valid_until": q.valid_until, "payment_terms_days": q.payment_terms_days, "terms": q.terms, "submitted_at": q.submitted_at,
            "complete": complete, "missing_items": missing_lines(q),
            "lines": [{"rfq_item_id": i.rfq_item_id, "line_no": i.line_no, "unit_price": i.unit_price, "line_total": i.line_total} for i in q.items],
            "scores": _scores_dict(s), "rank": s.rank, "lowest_price": s.lowest_price, "fastest": s.fastest,
            "within_budget": (q.total_amount <= rfq.budget_amount) if (complete and q.currency == rfq.currency) else None,
            "evaluation": None if ev is None else {"compliance_score": ev.compliance_score, "compliance_note": ev.compliance_note, "terms_score": ev.terms_score,
                                                  "terms_note": ev.terms_note, "evaluator_name": ev.evaluator_name, "version": ev.version, "updated_at": ev.updated_at},
        })
    currencies = sorted({r["currency"] for r in rows})
    rows.sort(key=lambda r: (r["currency"], r["rank"] is None, r["rank"] or 0, r["total_amount"]))
    sel = active_selection(db, rfq.id)
    return {
        "rfq": rfq, "currencies": currencies, "mixed_currencies": len(currencies) > 1,
        "note": "These quotations are in more than one currency. Prices are compared only within the same currency; nothing is converted." if len(currencies) > 1 else None,
        "weights": WEIGHTS, "vendor_info_available": info, "quotations": rows, "selection": sel,
        "can_select": sel is None and rfq.status in (RfqStatus.CLOSED.value, RfqStatus.ISSUED.value), "can_revoke": sel is not None,
    }


def evaluate(db: Session, principal: TokenClaims, rfq_id: str, quotation_id: str, body: EvaluationIn) -> Evaluation:
    rfq = get_rfq(db, rfq_id, lock=True)
    require_open(rfq)
    if rfq.status == RfqStatus.AWARDED.value:
        raise err(409, "Evaluations are locked while the RFQ is awarded. Revoke the award to change them.")
    q = db.scalar(select(Quotation).where(Quotation.id == quotation_id, Quotation.rfq_id == rfq.id))
    if q is None or q.status not in LIVE_QUOTATION:
        raise err(404, "Quotation not found.")
    if body.compliance_score is None and body.terms_score is None:
        raise err(422, "Enter at least one score.")
    ev = db.scalar(select(Evaluation).where(Evaluation.quotation_id == q.id))
    if ev is not None:
        if body.version is None or body.version != ev.version:
            raise err(409, "This evaluation was changed somewhere else. Reload it and try again.")
        ev.version += 1
    else:
        ev = Evaluation(rfq_id=rfq.id, quotation_id=q.id, version=1, evaluator_id=principal.sub, evaluator_name=principal.name or "Unknown")
        db.add(ev)
    ev.compliance_score, ev.compliance_note, ev.terms_score, ev.terms_note = body.compliance_score, body.compliance_note, body.terms_score, body.terms_note
    ev.evaluator_id, ev.evaluator_name = principal.sub, principal.name or "Unknown"
    log_history(rfq, principal, "evaluated", rfq.status, f"Evaluated {q.vendor_name}: compliance {body.compliance_score if body.compliance_score is not None else 'not scored'}, "
                f"terms {body.terms_score if body.terms_score is not None else 'not scored'}")
    event(db, "quotation_evaluated", rfq, actor_id=principal.sub, quotation_id=q.id)
    commit(db)
    db.refresh(ev)
    return ev


def select_supplier(db: Session, principal: TokenClaims, rfq_id: str, body: SelectIn, clients: Clients) -> Selection:
    """Awards the RFQ. The RFQ row is locked, and a unique index on `active_rfq_id` means two simultaneous awards cannot both succeed."""
    rfq = get_rfq(db, rfq_id, lock=True)
    existing = active_selection(db, rfq.id)
    if existing is not None:
        if existing.quotation_id == body.quotation_id:
            return existing  # the same request repeated: already done, nothing changes
        raise err(409, f"This RFQ is already awarded to {existing.vendor_name}. Revoke that award before selecting another supplier.")
    if rfq.status not in (RfqStatus.CLOSED.value, RfqStatus.ISSUED.value):
        raise err(409, f"A supplier cannot be selected while the RFQ is {rfq.status}.")
    now = utcnow()
    if rfq.status == RfqStatus.ISSUED.value:
        if rfq.deadline > now:
            raise err(409, "The deadline has not passed. Close the RFQ first if you want to stop taking quotations early.")
        previous = rfq.status
        rfq.status, rfq.closed_at = RfqStatus.CLOSED.value, now
        rfq.version += 1
        log_history(rfq, principal, "closed", previous, "Closed automatically because the deadline passed")
    q = db.scalar(select(Quotation).where(Quotation.id == body.quotation_id, Quotation.rfq_id == rfq.id))
    if q is None or q.status != QuotationStatus.SUBMITTED.value:
        raise err(422, "Select a submitted quotation from this RFQ.")
    if not is_complete(q) and not body.acknowledge_missing_items:
        raise err(422, f"This quotation does not price items {', '.join(map(str, missing_lines(q)))}. Confirm that you accept the missing items to select it.")
    found = vendor_lookup(clients, [q.vendor_id])  # 503 if the vendor service is down: an award is never made without checking eligibility now
    status = found.get(q.vendor_id, {}).get("status")
    if status != "verified":
        raise err(409, f"{q.vendor_name} is {status or 'not found'} in the vendor directory and cannot be awarded an order.")
    quotes = _open_quotations(db, rfq)
    evals = _evals(db, rfq)
    scored = score(_candidates(quotes, evals))
    ev = evals.get(q.id)
    snapshot = {"weights": WEIGHTS, "scores": {k: (str(v) if isinstance(v, Decimal) else v) for k, v in _scores_dict(scored[q.id]).items()}, "rank": scored[q.id].rank,
                "vendor_status": status, "compared_quotations": len(quotes),
                "evaluation": None if ev is None else {"compliance_score": ev.compliance_score, "compliance_note": ev.compliance_note, "terms_score": ev.terms_score,
                                                      "terms_note": ev.terms_note, "evaluator_name": ev.evaluator_name}}
    seq = (db.scalar(select(func.max(Selection.seq)).where(Selection.rfq_id == rfq.id)) or 0) + 1
    sel = Selection(rfq_id=rfq.id, seq=seq, quotation_id=q.id, vendor_id=q.vendor_id, vendor_name=q.vendor_name, active_rfq_id=rfq.id, justification=body.justification,
                    acknowledged_missing_items=not is_complete(q), currency=q.currency, total_amount=q.total_amount, score_snapshot=json.dumps(snapshot, default=str),
                    selected_by_id=principal.sub, selected_by_name=principal.name or "Unknown", selected_at=now)
    db.add(sel)
    commit(db, flush_only=True)  # a second award for this RFQ fails here with a clear 409
    for other in quotes:
        other.status = QuotationStatus.SELECTED.value if other.id == q.id else QuotationStatus.NOT_SELECTED.value
    previous = rfq.status
    rfq.status = RfqStatus.AWARDED.value
    rfq.version += 1
    log_history(rfq, principal, "awarded", previous, f"Awarded to {q.vendor_name}")
    event(db, "supplier_selected", rfq, actor_id=principal.sub, selection_id=sel.id, quotation_id=q.id, vendor_id=q.vendor_id,
          total_amount=str(q.total_amount), currency=q.currency)  # Phase 7 creates the purchase order from this; Phase 10 notifies the vendors
    commit(db)
    db.refresh(sel)
    return sel


def revoke(db: Session, principal: TokenClaims, rfq_id: str, reason: str) -> Selection:
    rfq = get_rfq(db, rfq_id, lock=True)
    sel = active_selection(db, rfq.id)
    if sel is None:
        raise err(409, "This RFQ has no award to revoke.")
    sel.status, sel.active_rfq_id = SelectionStatus.REVOKED.value, None
    sel.revoked_by_name, sel.revoked_at, sel.revoke_reason = principal.name or "Unknown", utcnow(), reason
    for q in _open_quotations(db, rfq):
        q.status = QuotationStatus.SUBMITTED.value
    previous = rfq.status
    rfq.status = RfqStatus.CLOSED.value
    rfq.version += 1
    log_history(rfq, principal, "award_revoked", previous, reason)
    event(db, "selection_revoked", rfq, actor_id=principal.sub, selection_id=sel.id, reason=reason)
    commit(db)
    db.refresh(sel)
    return sel


def selection_history(db: Session, rfq_id: str) -> list[Selection]:
    get_rfq(db, rfq_id)
    return list(db.scalars(select(Selection).where(Selection.rfq_id == rfq_id).order_by(Selection.seq)))


def award_ref(db: Session, rfq_id: str) -> AwardRef:
    rfq = db.scalar(select(Rfq).where(Rfq.id == rfq_id))
    sel = active_selection(db, rfq_id) if rfq else None
    if rfq is None or sel is None:
        raise err(404, "This RFQ has no active award.")
    q = db.scalar(select(Quotation).where(Quotation.id == sel.quotation_id))
    if q is None:
        raise err(404, "This RFQ has no active award.")
    by_item = {i.id: i for i in rfq.items}
    return AwardRef(
        selection_id=sel.id, rfq_id=rfq.id, rfq_number=rfq.number, rfq_title=rfq.title, purchase_request_id=rfq.purchase_request_id,
        purchase_request_number=rfq.purchase_request_number, needed_by=rfq.needed_by, vendor_id=q.vendor_id, vendor_number=q.vendor_number, vendor_name=q.vendor_name,
        quotation_id=q.id, quotation_number=q.number, currency=q.currency, total_amount=q.total_amount, lead_time_days=q.lead_time_days or 0,
        valid_until=q.valid_until, payment_terms_days=q.payment_terms_days, terms=q.terms,
        items=[AwardItem(line_no=i.line_no, rfq_item_id=i.rfq_item_id, description=by_item[i.rfq_item_id].description, specification=by_item[i.rfq_item_id].specification,
                         quantity=i.quantity, unit=by_item[i.rfq_item_id].unit, unit_price=i.unit_price, line_total=i.line_total) for i in q.items],
        acknowledged_missing_items=sel.acknowledged_missing_items, justification=sel.justification, selected_by_name=sel.selected_by_name, selected_at=sel.selected_at)


