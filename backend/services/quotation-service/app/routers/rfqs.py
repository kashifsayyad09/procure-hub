from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from procurehub_common.tokens import TokenClaims
from sqlalchemy.orm import Session

from .. import evaluation, outputs, service
from ..common import Clients, quotations_open, vendor_for_user
from ..database import get_db
from ..deps import require_any_permission
from ..models import RfqStatus, utcnow
from ..schemas import (
    CompareRfq,
    ComparisonOut,
    EligiblePage,
    EvaluationIn,
    EvaluationOut,
    ExtendIn,
    InviteIn,
    QuotationList,
    ReasonIn,
    RevokeIn,
    RfqCounts,
    RfqCreate,
    RfqOut,
    RfqPage,
    RfqUpdate,
    SelectIn,
    SelectionHistory,
    SelectionOut,
    StaffItemOut,
    VendorRfqOut,
    VendorRfqPage,
)

router = APIRouter(prefix="/api/v1/rfqs", tags=["rfqs"])

STAFF = require_any_permission("rfq:manage")
COMPARER = require_any_permission("quotation:compare")
INVITED = require_any_permission("rfq:read_invited")


def clients(request: Request) -> Clients:
    return request.app.state.clients


def vendor_ctx(principal: TokenClaims = Depends(INVITED), c: Clients = Depends(clients)) -> dict:
    """The signed-in vendor user's vendor record, from the vendor service. Nothing about who the vendor is comes from the browser."""
    return vendor_for_user(c, principal)


# ---- procurement: RFQs -----------------------------------------------------------------------------
@router.get("/summary", response_model=RfqCounts)
def get_summary(_: TokenClaims = Depends(STAFF), db: Session = Depends(get_db)):
    counts, waiting = service.summary(db)
    return RfqCounts(counts=counts, awaiting_comparison=waiting)


@router.get("/eligible-requests", response_model=EligiblePage)
def eligible(q: str | None = Query(default=None, max_length=100), page: int = Query(default=1, ge=1), page_size: int = Query(default=10, ge=1, le=50),
             _: TokenClaims = Depends(STAFF), db: Session = Depends(get_db), c: Clients = Depends(clients)):
    d = service.eligible_requests(db, c, q, page, page_size)
    return EligiblePage(items=[outputs.eligible_out(r) for r in d["items"]], total=d["total"], page=d["page"], page_size=d["page_size"])


@router.get("", response_model=RfqPage)
def list_rfqs(status_: RfqStatus | None = Query(default=None, alias="status"), q: str | None = Query(default=None, max_length=100),
              sort: Literal["created_at", "deadline", "number", "title"] = "created_at", order: Literal["asc", "desc"] = "desc",
              page: int = Query(default=1, ge=1), page_size: int = Query(default=20, ge=1, le=100), _: TokenClaims = Depends(STAFF), db: Session = Depends(get_db)):
    rows, total = service.list_rfqs(db, status_=status_.value if status_ else None, q=q, sort=sort, order=order, page=page, page_size=page_size)
    counts = service.submitted_counts(db, [r.id for r in rows])
    return RfqPage(items=[outputs.rfq_summary(r, counts.get(r.id, 0)) for r in rows], total=total, page=page, page_size=page_size)


@router.post("", response_model=RfqOut, status_code=201)
def create_rfq(body: RfqCreate, request: Request, principal: TokenClaims = Depends(STAFF), db: Session = Depends(get_db), c: Clients = Depends(clients)):
    return outputs.rfq_out(db, service.create_rfq(db, principal, body, c, request.app.state.settings))


# ---- vendor: invited RFQs (declared before /{rfq_id} so the words are not read as ids) ---------------
@router.get("/invited", response_model=VendorRfqPage)
def list_invited(page: int = Query(default=1, ge=1), page_size: int = Query(default=20, ge=1, le=100), vendor: dict = Depends(vendor_ctx), db: Session = Depends(get_db)):
    rows, total = service.list_invited(db, vendor, page, page_size)
    return VendorRfqPage(items=[outputs.vendor_rfq_summary(r, i, q, vendor) for r, i, q in rows], total=total, page=page, page_size=page_size)


@router.get("/invited/{rfq_id}", response_model=VendorRfqOut)
def get_invited(rfq_id: str, vendor: dict = Depends(vendor_ctx), db: Session = Depends(get_db)):
    rfq, inv = service.invitation_for(db, vendor["id"], rfq_id)
    q = service.quotation_of(db, rfq.id, vendor["id"])
    return outputs.vendor_rfq_out(rfq, inv, q, vendor)


@router.post("/invited/{rfq_id}/decline", response_model=VendorRfqOut)
def decline(rfq_id: str, vendor: dict = Depends(vendor_ctx), db: Session = Depends(get_db)):
    service.decline(db, vendor, rfq_id)
    rfq, inv = service.invitation_for(db, vendor["id"], rfq_id)
    q = service.quotation_of(db, rfq.id, vendor["id"])
    return outputs.vendor_rfq_out(rfq, inv, q, vendor)


# ---- procurement: one RFQ --------------------------------------------------------------------------
@router.get("/{rfq_id}", response_model=RfqOut)
def get_rfq(rfq_id: str, _: TokenClaims = Depends(STAFF), db: Session = Depends(get_db)):
    return outputs.rfq_out(db, service.get_rfq(db, rfq_id))


@router.put("/{rfq_id}", response_model=RfqOut)
def update_rfq(rfq_id: str, body: RfqUpdate, request: Request, principal: TokenClaims = Depends(STAFF), db: Session = Depends(get_db)):
    return outputs.rfq_out(db, service.update_rfq(db, principal, rfq_id, body, request.app.state.settings))


@router.post("/{rfq_id}/publish", response_model=RfqOut)
def publish(rfq_id: str, request: Request, principal: TokenClaims = Depends(STAFF), db: Session = Depends(get_db), c: Clients = Depends(clients)):
    return outputs.rfq_out(db, service.publish(db, principal, rfq_id, c, request.app.state.settings))


@router.post("/{rfq_id}/close", response_model=RfqOut)
def close(rfq_id: str, principal: TokenClaims = Depends(STAFF), db: Session = Depends(get_db)):
    return outputs.rfq_out(db, service.close(db, principal, rfq_id))


@router.post("/{rfq_id}/cancel", response_model=RfqOut)
def cancel(rfq_id: str, body: ReasonIn, principal: TokenClaims = Depends(STAFF), db: Session = Depends(get_db)):
    return outputs.rfq_out(db, service.cancel(db, principal, rfq_id, body.reason))


@router.post("/{rfq_id}/extend", response_model=RfqOut)
def extend(rfq_id: str, body: ExtendIn, request: Request, principal: TokenClaims = Depends(STAFF), db: Session = Depends(get_db)):
    return outputs.rfq_out(db, service.extend(db, principal, rfq_id, body, request.app.state.settings))


# ---- invitations -----------------------------------------------------------------------------------
@router.post("/{rfq_id}/invitations", response_model=RfqOut, status_code=201)
def invite(rfq_id: str, body: InviteIn, principal: TokenClaims = Depends(STAFF), db: Session = Depends(get_db), c: Clients = Depends(clients)):
    return outputs.rfq_out(db, service.invite(db, principal, rfq_id, body.vendor_ids, c))


@router.post("/{rfq_id}/invitations/{invitation_id}/withdraw", response_model=RfqOut)
def withdraw_invitation(rfq_id: str, invitation_id: str, principal: TokenClaims = Depends(STAFF), db: Session = Depends(get_db)):
    return outputs.rfq_out(db, service.withdraw_invitation(db, principal, rfq_id, invitation_id))


# ---- quotations, comparison, evaluation, selection ---------------------------------------------------
@router.get("/{rfq_id}/quotations", response_model=QuotationList)
def list_quotations(rfq_id: str, _: TokenClaims = Depends(COMPARER), db: Session = Depends(get_db)):
    rfq = service.get_rfq(db, rfq_id)
    rows = outputs.quotation_rows(db, rfq)
    return QuotationList(quotations_open=quotations_open(rfq, utcnow()), rows=rows)


@router.get("/{rfq_id}/comparison", response_model=ComparisonOut)
def comparison(rfq_id: str, _: TokenClaims = Depends(COMPARER), db: Session = Depends(get_db), c: Clients = Depends(clients)):
    d = evaluation.compare(db, rfq_id, c)
    rfq = d["rfq"]
    return ComparisonOut(
        rfq=CompareRfq(id=rfq.id, number=rfq.number, title=rfq.title, status=rfq.status, currency=rfq.currency, deadline=rfq.deadline, budget_amount=rfq.budget_amount,
                       version=rfq.version, items=[StaffItemOut.model_validate(i) for i in rfq.items]),
        currencies=d["currencies"], mixed_currencies=d["mixed_currencies"], note=d["note"], weights=d["weights"], vendor_info_available=d["vendor_info_available"],
        quotations=d["quotations"], selection=SelectionOut.model_validate(d["selection"]) if d["selection"] else None, can_select=d["can_select"], can_revoke=d["can_revoke"])


@router.put("/{rfq_id}/evaluations/{quotation_id}", response_model=EvaluationOut)
def evaluate(rfq_id: str, quotation_id: str, body: EvaluationIn, principal: TokenClaims = Depends(COMPARER), db: Session = Depends(get_db)):
    return EvaluationOut.model_validate(_ev_out(evaluation.evaluate(db, principal, rfq_id, quotation_id, body)))


def _ev_out(ev) -> dict:
    return {"compliance_score": ev.compliance_score, "compliance_note": ev.compliance_note, "terms_score": ev.terms_score, "terms_note": ev.terms_note,
            "evaluator_name": ev.evaluator_name, "version": ev.version, "updated_at": ev.updated_at}


@router.post("/{rfq_id}/selection", response_model=SelectionOut)
def select(rfq_id: str, body: SelectIn, principal: TokenClaims = Depends(STAFF), db: Session = Depends(get_db), c: Clients = Depends(clients)):
    return SelectionOut.model_validate(evaluation.select_supplier(db, principal, rfq_id, body, c))


@router.get("/{rfq_id}/selection", response_model=SelectionOut)
def get_selection(rfq_id: str, _: TokenClaims = Depends(STAFF), db: Session = Depends(get_db)):
    service.get_rfq(db, rfq_id)
    sel = service.active_selection(db, rfq_id)
    if sel is None:
        raise HTTPException(404, "This RFQ has no award.")
    return SelectionOut.model_validate(sel)


@router.get("/{rfq_id}/selection/history", response_model=SelectionHistory)
def selection_history(rfq_id: str, _: TokenClaims = Depends(STAFF), db: Session = Depends(get_db)):
    return SelectionHistory(items=[SelectionOut.model_validate(s) for s in evaluation.selection_history(db, rfq_id)])


@router.post("/{rfq_id}/selection/revoke", response_model=SelectionOut)
def revoke(rfq_id: str, body: RevokeIn, principal: TokenClaims = Depends(STAFF), db: Session = Depends(get_db)):
    return SelectionOut.model_validate(evaluation.revoke(db, principal, rfq_id, body.reason))
