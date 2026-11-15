"""Turns database rows into API responses. What each audience may see is decided here: vendors never get budgets, estimates or other vendors."""
from sqlalchemy import select
from sqlalchemy.orm import Session

from . import service
from .common import quotations_open
from .models import Invitation, InvitationStatus, Quotation, QuotationStatus, Rfq, utcnow
from .schemas import (
    EligibleRequestOut,
    HistoryOut,
    InvitationOut,
    ItemOut,
    MyQuotationRow,
    QuotationOut,
    QuotationRowOut,
    QuoteLineOut,
    RfqOut,
    RfqSummaryOut,
    SelectionOut,
    StaffItemOut,
    VendorQuotationSummary,
    VendorRfqOut,
    VendorRfqSummaryOut,
)


def rfq_summary(rfq: Rfq, submitted: int) -> RfqSummaryOut:
    return RfqSummaryOut(
        id=rfq.id, number=rfq.number, title=rfq.title, purchase_request_id=rfq.purchase_request_id, purchase_request_number=rfq.purchase_request_number,
        department=rfq.department, status=rfq.status, currency=rfq.currency, deadline=rfq.deadline, deadline_passed=rfq.deadline <= utcnow(),
        invited=len([i for i in rfq.invitations if i.status == InvitationStatus.INVITED.value]), submitted=submitted,
        created_by_name=rfq.created_by_name, created_at=rfq.created_at)


def rfq_out(db: Session, rfq: Rfq) -> RfqOut:
    now = utcnow()
    quotes = {q.vendor_id: q.status for q in db.scalars(select(Quotation).where(Quotation.rfq_id == rfq.id))}
    sel = service.active_selection(db, rfq.id)
    submitted = len([s for s in quotes.values() if s != QuotationStatus.DRAFT.value])
    invitations = [InvitationOut.model_validate({**{c: getattr(i, c) for c in InvitationOut.model_fields if c != "quotation_status"}, "quotation_status": quotes.get(i.vendor_id)})
                   for i in rfq.invitations]
    return RfqOut(
        **rfq_summary(rfq, submitted).model_dump(), description=rfq.description, requirements=rfq.requirements, needed_by=rfq.needed_by, budget_amount=rfq.budget_amount,
        version=rfq.version, issued_at=rfq.issued_at, closed_at=rfq.closed_at, cancel_reason=rfq.cancel_reason, updated_at=rfq.updated_at,
        items=[StaffItemOut.model_validate(i) for i in rfq.items], invitations=invitations, history=[HistoryOut.model_validate(h) for h in rfq.history],
        quotations_open=quotations_open(rfq, now), selection=SelectionOut.model_validate(sel) if sel else None,
        actions=service.rfq_actions(rfq, now, sel is not None))  # type: ignore[arg-type]


def eligible_out(d: dict) -> EligibleRequestOut:
    return EligibleRequestOut(id=d["id"], number=d["number"], title=d["title"], department=d.get("department") or "", priority=d["priority"], currency=d["currency"],
                              total_amount=d["total_amount"], needed_by=d.get("needed_by"), decided_at=d.get("decided_at"), decided_by_name=d.get("decided_by_name"),
                              item_count=d["item_count"], rfq_id=d["rfq_id"], rfq_number=d["rfq_number"])


def quotation_out(q: Quotation, rfq: Rfq, inv: Invitation | None = None, vendor: dict | None = None) -> QuotationOut:
    can_edit, can_submit, can_withdraw = service.quotation_flags(q, rfq, inv, vendor)
    return QuotationOut(
        id=q.id, number=q.number, rfq_id=rfq.id, rfq_number=rfq.number, rfq_title=rfq.title, vendor_id=q.vendor_id, vendor_name=q.vendor_name, currency=q.currency,
        lead_time_days=q.lead_time_days, valid_until=q.valid_until, payment_terms_days=q.payment_terms_days, terms=q.terms, total_amount=q.total_amount, status=q.status,
        revision=q.revision, version=q.version, submitted_at=q.submitted_at, updated_at=q.updated_at, items=[QuoteLineOut.model_validate(i) for i in q.items],
        complete=service.is_complete(q), missing_items=service.missing_lines(q),
        problems=service.problems_for_submit(q, rfq) if q.status == QuotationStatus.DRAFT.value else [], can_edit=can_edit, can_submit=can_submit, can_withdraw=can_withdraw)


def quotation_rows(db: Session, rfq: Rfq) -> list[QuotationRowOut]:
    """One row per invited vendor. Amounts appear only when quotations are open, and never for a draft."""
    is_open = quotations_open(rfq, utcnow())
    quotes = {q.vendor_id: q for q in db.scalars(select(Quotation).where(Quotation.rfq_id == rfq.id))}
    rows = []
    for inv in rfq.invitations:
        q = quotes.get(inv.vendor_id)
        shown = q is not None and q.status != QuotationStatus.DRAFT.value and is_open
        rows.append(QuotationRowOut(
            id=q.id if shown and q else None, number=q.number if shown and q else None, vendor_id=inv.vendor_id, vendor_name=inv.vendor_name, invitation_status=inv.status,
            status=q.status if q else None, submitted_at=q.submitted_at if q and q.status != QuotationStatus.DRAFT.value else None,
            currency=q.currency if shown and q else None, total_amount=q.total_amount if shown and q else None, lead_time_days=q.lead_time_days if shown and q else None))
    return rows


def _vendor_quote(q: Quotation | None) -> VendorQuotationSummary | None:
    return None if q is None else VendorQuotationSummary(id=q.id, number=q.number, status=q.status, total_amount=q.total_amount, currency=q.currency, updated_at=q.updated_at)


def vendor_rfq_summary(rfq: Rfq, inv: Invitation, q: Quotation | None, vendor: dict) -> VendorRfqSummaryOut:
    now = utcnow()
    return VendorRfqSummaryOut(id=rfq.id, number=rfq.number, title=rfq.title, status=rfq.status, currency=rfq.currency, deadline=rfq.deadline, deadline_passed=rfq.deadline <= now,
                               invitation_status=inv.status, quotation=_vendor_quote(q), can_quote=service.quote_block(rfq, inv, vendor, now) is None)


def vendor_rfq_out(rfq: Rfq, inv: Invitation, q: Quotation | None, vendor: dict) -> VendorRfqOut:
    block = service.quote_block(rfq, inv, vendor, utcnow())
    return VendorRfqOut(**vendor_rfq_summary(rfq, inv, q, vendor).model_dump(), description=rfq.description, requirements=rfq.requirements, needed_by=rfq.needed_by,
                        items=[ItemOut.model_validate(i) for i in rfq.items], blocked_reason=block[1] if block else None, issued_at=rfq.issued_at)


def my_row(q: Quotation, rfq: Rfq) -> MyQuotationRow:
    return MyQuotationRow(id=q.id, number=q.number, rfq_id=rfq.id, rfq_number=rfq.number, rfq_title=rfq.title, status=q.status, currency=q.currency,
                          total_amount=q.total_amount, deadline=rfq.deadline, updated_at=q.updated_at)
