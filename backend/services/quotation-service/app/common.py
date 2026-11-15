"""Helpers shared by the RFQ, quotation and selection code: errors, outside-service calls, numbering, history and the outbox."""
import json
import logging
from dataclasses import dataclass
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from fastapi import HTTPException
from procurehub_common.service_client import ServiceClient, ServiceRejected, ServiceUnavailable
from procurehub_common.tokens import TokenClaims
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .models import NumberSequence, QuotationEvent, Rfq, RfqHistory, RfqStatus

log = logging.getLogger("quotations")
CENT = Decimal("0.01")


def err(code: int, detail: str | list[str]) -> HTTPException:
    return HTTPException(code, detail)


def line_total(quantity: Decimal, unit_price: Decimal) -> Decimal:
    return (quantity * unit_price).quantize(CENT, rounding=ROUND_HALF_UP)


@dataclass
class Clients:
    """Calls to the other services. Either can be missing (not configured); using a missing one answers 503, never a guess."""

    vendors: ServiceClient | None = None
    requests: ServiceClient | None = None

    def vendor(self) -> ServiceClient:
        if self.vendors is None:
            raise err(503, "The vendor service is not configured.")
        return self.vendors

    def request_service(self) -> ServiceClient:
        if self.requests is None:
            raise err(503, "The purchase request service is not configured.")
        return self.requests


def call(fn, *args, **kwargs) -> Any:
    """Runs a call to another service. A service that is down is a 503 the caller may retry; a refusal is passed on as 502
    because it means the contract between the services is broken, not that the user did something wrong."""
    try:
        return fn(*args, **kwargs)
    except ServiceUnavailable:
        raise err(503, "A service this step depends on is not available right now. Try again in a moment.") from None


def vendor_lookup(clients: Clients, ids: list[str]) -> dict[str, dict]:
    rows = call(clients.vendor().post, "/internal/v1/vendors/lookup", {"ids": ids}) or []
    return {r["id"]: r for r in rows}


def vendor_for_user(clients: Clients, principal: TokenClaims) -> dict:
    """Turns the signed-in vendor user into their vendor record. The id comes from the vendor service, never from the browser."""
    try:
        return call(clients.vendor().get, f"/internal/v1/vendors/by-owner/{principal.sub}")
    except ServiceRejected as e:
        if e.status_code == 404:
            raise err(403, "Register your vendor profile first.") from None
        raise err(502, "The vendor service refused the request.") from None


def next_number(db: Session, kind: str, year: int) -> str:
    """RFQ-<year>-<6 digits> or QTN-<year>-<6 digits>. Call before adding anything else to the session."""
    for _ in range(4):
        seq = db.scalar(select(NumberSequence).where(NumberSequence.kind == kind, NumberSequence.year == year).with_for_update())
        if seq is not None:
            seq.last_value += 1
            db.flush()
            return f"{kind}-{year}-{seq.last_value:06d}"
        db.add(NumberSequence(kind=kind, year=year, last_value=0))
        try:
            db.flush()
        except IntegrityError:  # another request created the counter first; try again and lock it
            db.rollback()
    raise RuntimeError("could not allocate a number")


def log_history(rfq: Rfq, principal: TokenClaims, action: str, from_status: str | None, note: str | None = None) -> None:
    rfq.history.append(RfqHistory(seq=len(rfq.history) + 1, action=action, from_status=from_status, to_status=rfq.status,
                                  actor_id=principal.sub, actor_name=principal.name or "Unknown", note=note))


def event(db: Session, kind: str, rfq: Rfq, **extra: Any) -> None:
    payload = {"rfq_id": rfq.id, "rfq_number": rfq.number, "status": rfq.status, **extra}
    db.add(QuotationEvent(type=kind, rfq_id=rfq.id, payload=json.dumps(payload, default=str)))


def quotations_open(rfq: Rfq, now: datetime) -> bool:
    """Prices are sealed while bidding is open. They open when the deadline has passed or procurement has closed the RFQ."""
    return rfq.status in (RfqStatus.CLOSED.value, RfqStatus.AWARDED.value) or (rfq.status == RfqStatus.ISSUED.value and rfq.deadline <= now)


def commit(db: Session, *, flush_only: bool = False) -> None:
    """The unique indexes are the last guard against two requests racing past the checks; a clash is a 409, not a 500."""
    try:
        db.flush() if flush_only else db.commit()
    except IntegrityError as exc:
        db.rollback()
        text = str(exc.orig).lower()
        if "active_request_id" in text:
            raise err(409, "This purchase request already has an RFQ in progress.") from None
        if "active_rfq_id" in text:
            raise err(409, "This RFQ already has an award. Revoke it before selecting another supplier.") from None
        if "uq_invitation" in text or "rfq_invitations" in text:
            raise err(409, "One of these vendors is already invited.") from None
        if "uq_quotation" in text or "quotations." in text:
            raise err(409, "You already have a quotation for this RFQ.") from None
        raise err(409, "This could not be saved because it clashes with an existing record.") from None
