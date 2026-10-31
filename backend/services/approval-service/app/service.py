"""Approval workflow rules. Routers stay thin; everything that decides who may do what lives here."""
import json
import logging
from datetime import datetime, timedelta
from decimal import Decimal

from fastapi import HTTPException, status
from procurehub_common.contracts.approval import ApprovalRegistration, CancelNotice, DecisionNotice, ManagerRef
from procurehub_common.service_client import ServiceClient, ServiceRejected, ServiceUnavailable
from procurehub_common.tokens import TokenClaims
from sqlalchemy import exists, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .models import Approval, ApprovalEvent, ApprovalHistory, ApprovalStep, utcnow
from .rules import levels_for

log = logging.getLogger("approvals")

SORTABLE = {"created_at": Approval.created_at, "total_amount": Approval.total_amount, "needed_by": Approval.needed_by,
            "request_number": Approval.request_number, "decided_at": Approval.decided_at}


def _err(code: int, detail: str) -> HTTPException:
    return HTTPException(code, detail)


def _event(db: Session, kind: str, ap: Approval, **extra) -> None:
    payload = {"approval_id": ap.id, "request_id": ap.request_id, "request_number": ap.request_number, "requester_id": ap.requester_id,
               "status": ap.status, "level": ap.current_level, **extra}
    db.add(ApprovalEvent(type=kind, approval_id=ap.id, payload=json.dumps(payload, default=str)))


def _note(ap: Approval, action: str, actor_name: str, *, actor_id: str | None = None, level: int | None = None, text: str | None = None) -> None:
    ap.history.append(ApprovalHistory(seq=len(ap.history) + 1, action=action, level=level, actor_id=actor_id, actor_name=actor_name, note=text))


def current_step(ap: Approval) -> ApprovalStep | None:
    return next((s for s in ap.steps if s.status == "pending"), None)


# ---- creating and cancelling workflows (called by the Purchase Request service) -------------------------
def register(db: Session, reg: ApprovalRegistration, thresholds: dict[str, list[Decimal]]) -> Approval:
    """Idempotent on request_id: registering the same request twice returns the first workflow."""
    existing = db.scalar(select(Approval).where(Approval.request_id == reg.request_id))
    if existing is not None:
        return existing
    levels = levels_for(reg.total_amount, reg.currency, thresholds)
    now = utcnow()
    ap = Approval(
        request_id=reg.request_id, request_number=reg.request_number, title=reg.title, justification=reg.justification, department=reg.department,
        priority=reg.priority, currency=reg.currency, total_amount=reg.total_amount, needed_by=reg.needed_by, requester_id=reg.requester_id,
        requester_name=reg.requester_name, requester_email=reg.requester_email, submitted_at=reg.submitted_at,
        items_json=json.dumps([i.model_dump(mode="json") for i in reg.items]), status="pending", current_level=1, total_levels=levels,
    )
    ap.steps = [ApprovalStep(level=n, status="pending" if n == 1 else "waiting", activated_at=now if n == 1 else None) for n in range(1, levels + 1)]
    _note(ap, "requested", reg.requester_name, actor_id=reg.requester_id, text=f"{levels} level{'s' if levels > 1 else ''} of approval required")
    db.add(ap)
    db.flush()
    _event(db, "approval.requested", ap, title=ap.title, total=str(ap.total_amount), currency=ap.currency, levels=levels)
    try:
        db.commit()
    except IntegrityError:  # a concurrent registration of the same request won
        db.rollback()
        return db.scalar(select(Approval).where(Approval.request_id == reg.request_id))  # type: ignore[return-value]
    log.info("approval_registered", extra={"event": "approval_registered", "approval_id": ap.id, "request_number": ap.request_number, "levels": levels})
    return ap


def cancel_by_request(db: Session, request_id: str, notice: CancelNotice) -> Approval | None:
    """Idempotent. Returns None if this service never heard of the request."""
    ap = db.scalar(select(Approval).where(Approval.request_id == request_id).with_for_update())
    if ap is None or ap.status != "pending":
        return ap
    ap.status = "cancelled"
    for s in ap.steps:
        if s.status in ("pending", "waiting"):
            s.status = "skipped"
    _note(ap, "cancelled", notice.actor_name, text=notice.reason or "Cancelled by the requester")
    _event(db, "approval.cancelled", ap)
    db.commit()
    return ap


# ---- who may act ---------------------------------------------------------------------------------------
def blocked_reason(ap: Approval, user: TokenClaims) -> tuple[int, str] | None:
    """None if the user may decide the current step; otherwise (http status, plain-language reason)."""
    step = current_step(ap)
    if ap.status != "pending" or step is None:
        return status.HTTP_409_CONFLICT, f"This request is already {ap.status}."
    if user.sub == ap.requester_id:
        return status.HTTP_403_FORBIDDEN, "You cannot decide your own request."
    if any(s.status == "approved" and s.decided_by_id == user.sub for s in ap.steps):
        return status.HTTP_403_FORBIDDEN, "A different manager must approve each level."
    if step.assigned_to_id and step.assigned_to_id != user.sub:
        return status.HTTP_403_FORBIDDEN, f"This approval was delegated to {step.assigned_to_name}."
    return None


def _lock(db: Session, approval_id: str) -> Approval:
    ap = db.scalar(select(Approval).where(Approval.id == approval_id).with_for_update())
    if ap is None:
        raise _err(status.HTTP_404_NOT_FOUND, "Approval not found.")
    return ap


def _require_actor(ap: Approval, user: TokenClaims) -> ApprovalStep:
    problem = blocked_reason(ap, user)
    if problem:
        raise _err(*problem)
    return current_step(ap)  # type: ignore[return-value]


# ---- decisions -----------------------------------------------------------------------------------------
def approve(db: Session, user: TokenClaims, approval_id: str, comment: str | None) -> Approval:
    ap = _lock(db, approval_id)
    step = _require_actor(ap, user)
    now = utcnow()
    step.status, step.decided_by_id, step.decided_by_name, step.decided_at, step.comment = "approved", user.sub, user.name, now, comment
    _note(ap, "approved", user.name, actor_id=user.sub, level=step.level, text=comment)
    if step.level < ap.total_levels:
        nxt = next(s for s in ap.steps if s.level == step.level + 1)
        nxt.status, nxt.activated_at = "pending", now
        ap.current_level = nxt.level
        _event(db, "approval.step_approved", ap, approved_level=step.level, actor=user.name)
    else:
        ap.status, ap.decided_at, ap.decision_sync = "approved", now, "pending"
        _event(db, "approval.approved", ap, actor=user.name)
    db.commit()
    log.info("approval_step_approved", extra={
        "event": "approval_step_approved", "approval_id": ap.id, "approval_level": step.level, "actor_id": user.sub, "final": ap.status == "approved"})
    return ap


def reject(db: Session, user: TokenClaims, approval_id: str, reason: str) -> Approval:
    ap = _lock(db, approval_id)
    step = _require_actor(ap, user)
    now = utcnow()
    step.status, step.decided_by_id, step.decided_by_name, step.decided_at, step.comment = "rejected", user.sub, user.name, now, reason
    for s in ap.steps:
        if s.status in ("pending", "waiting") and s is not step:
            s.status = "skipped"
    ap.status, ap.decided_at, ap.decision_sync = "rejected", now, "pending"
    _note(ap, "rejected", user.name, actor_id=user.sub, level=step.level, text=reason)
    _event(db, "approval.rejected", ap, actor=user.name, reason=reason)
    db.commit()
    log.info("approval_rejected", extra={"event": "approval_rejected", "approval_id": ap.id, "approval_level": step.level, "actor_id": user.sub})
    return ap


def delegate(db: Session, user: TokenClaims, approval_id: str, target: ManagerRef, note: str | None) -> Approval:
    ap = _lock(db, approval_id)
    step = _require_actor(ap, user)
    if target.id == user.sub:
        raise _err(status.HTTP_422_UNPROCESSABLE_CONTENT, "Choose a different manager.")
    if target.id == ap.requester_id:
        raise _err(status.HTTP_422_UNPROCESSABLE_CONTENT, "You cannot delegate to the person who made the request.")
    if any(s.status == "approved" and s.decided_by_id == target.id for s in ap.steps):
        raise _err(status.HTTP_422_UNPROCESSABLE_CONTENT, f"{target.full_name} already approved an earlier level.")
    step.assigned_to_id, step.assigned_to_name = target.id, target.full_name
    _note(ap, "delegated", user.name, actor_id=user.sub, level=step.level, text=f"To {target.full_name}" + (f": {note}" if note else ""))
    _event(db, "approval.delegated", ap, actor=user.name, delegate_id=target.id, delegate_name=target.full_name)
    db.commit()
    log.info("approval_delegated", extra={"event": "approval_delegated", "approval_id": ap.id, "approval_level": step.level, "actor_id": user.sub, "delegate_id": target.id})
    return ap


# ---- keeping the Purchase Request service in step -------------------------------------------------------
def sync_decision(db: Session, client: ServiceClient | None, ap: Approval) -> None:
    """Tells the Purchase Request service about a final decision. Retried by the background loop until it gets through."""
    if client is None or ap.decision_sync != "pending":
        return
    decided = [s for s in ap.steps if s.decided_by_id]
    final = max(decided, key=lambda s: s.level)
    notice = DecisionNotice(decision=ap.status, actor_id=final.decided_by_id, actor_name=final.decided_by_name or "Manager",  # type: ignore[arg-type]
                            note=final.comment, decided_at=ap.decided_at or utcnow())
    ap.sync_attempts += 1
    try:
        client.post(f"/internal/v1/purchase-requests/{ap.request_id}/decision", json=notice.model_dump(mode="json"))
    except ServiceUnavailable as e:
        ap.last_sync_error = str(e)[:300]
        db.commit()
        log.warning("decision_sync_deferred", extra={"event": "decision_sync_deferred", "approval_id": ap.id, "attempts": ap.sync_attempts})
        return
    except ServiceRejected as e:  # for example the requester cancelled in the meantime; retrying cannot help
        ap.decision_sync, ap.last_sync_error = "conflict", f"{e.status_code}: {e.detail}"[:300]
        _note(ap, "sync_conflict", "System", text=ap.last_sync_error)
        _event(db, "approval.sync_conflict", ap, error=ap.last_sync_error)
        db.commit()
        log.error("decision_sync_conflict", extra={"event": "decision_sync_conflict", "approval_id": ap.id, "error": ap.last_sync_error})
        return
    ap.decision_sync, ap.last_sync_error = "synced", None
    db.commit()
    log.info("decision_synced", extra={"event": "decision_synced", "approval_id": ap.id, "attempts": ap.sync_attempts})


def escalate_overdue(db: Session, hours: int) -> int:
    """Flags pending steps that have waited longer than `hours`. Nothing else changes: any eligible manager can still decide."""
    cutoff = utcnow() - timedelta(hours=hours)
    rows = db.scalars(select(ApprovalStep).join(Approval, Approval.id == ApprovalStep.approval_id)
                      .where(ApprovalStep.status == "pending", ApprovalStep.escalated_at.is_(None), ApprovalStep.activated_at < cutoff, Approval.status == "pending")).all()
    for step in rows:
        ap = db.get(Approval, step.approval_id)
        step.escalated_at = utcnow()
        _note(ap, "escalated", "System", level=step.level, text=f"No decision after {hours} hours")
        _event(db, "approval.escalated", ap, level=step.level, hours=hours)
    if rows:
        db.commit()
        log.warning("approvals_escalated", extra={"event": "approvals_escalated", "count": len(rows)})
    return len(rows)


def reconcile_once(db: Session, client: ServiceClient | None, escalation_hours: int, limit: int = 50) -> tuple[int, int]:
    """Returns (decisions delivered, approvals escalated)."""
    delivered = 0
    for ap in db.scalars(select(Approval).where(Approval.decision_sync == "pending").order_by(Approval.decided_at).limit(limit)).all():
        sync_decision(db, client, ap)
        delivered += ap.decision_sync == "synced"
    return delivered, escalate_overdue(db, escalation_hours)


# ---- queries -------------------------------------------------------------------------------------------
def _queue_filter(user: TokenClaims):
    mine_or_open = exists().where(ApprovalStep.approval_id == Approval.id, ApprovalStep.status == "pending",
                                  or_(ApprovalStep.assigned_to_id.is_(None), ApprovalStep.assigned_to_id == user.sub))
    already_approved = exists().where(ApprovalStep.approval_id == Approval.id, ApprovalStep.decided_by_id == user.sub, ApprovalStep.status == "approved")
    return (Approval.status == "pending", Approval.requester_id != user.sub, mine_or_open, ~already_approved)


def _like(term: str) -> str:
    return "%" + term.lower().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"


def list_approvals(db: Session, user: TokenClaims, *, view: str, status_: str | None, priority: str | None, q: str | None, sort: str, order: str,
                   page: int, page_size: int) -> tuple[list[Approval], int]:
    stmt = select(Approval)
    if view == "queue":
        stmt = stmt.where(*_queue_filter(user))
    elif view == "mine":
        stmt = stmt.where(exists().where(ApprovalStep.approval_id == Approval.id, or_(ApprovalStep.decided_by_id == user.sub, ApprovalStep.assigned_to_id == user.sub)))
    if status_:
        stmt = stmt.where(Approval.status == status_)
    if priority:
        stmt = stmt.where(Approval.priority == priority)
    if q and q.strip():
        like = _like(q.strip())
        stmt = stmt.where(or_(func.lower(Approval.request_number).like(like, escape="\\"), func.lower(Approval.title).like(like, escape="\\"),
                              func.lower(Approval.requester_name).like(like, escape="\\")))
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    col = SORTABLE[sort]
    rows = db.scalars(stmt.order_by(col.desc() if order == "desc" else col.asc(), Approval.id).offset((page - 1) * page_size).limit(page_size)).all()
    return list(rows), total


def get_approval(db: Session, approval_id: str) -> Approval:
    ap = db.get(Approval, approval_id)
    if ap is None:
        raise _err(status.HTTP_404_NOT_FOUND, "Approval not found.")
    return ap


def _count(db: Session, stmt) -> int:
    return db.scalar(select(func.count()).select_from(stmt.subquery())) or 0


def summary(db: Session, user: TokenClaims):
    queue = _queue_filter(user)
    waiting = _count(db, select(Approval.id).where(*queue))
    escalated_step = exists().where(ApprovalStep.approval_id == Approval.id, ApprovalStep.status == "pending", ApprovalStep.escalated_at.is_not(None))
    overdue = _count(db, select(Approval.id).where(*queue, escalated_step))
    delegated = _count(db, select(ApprovalStep.id).join(Approval, Approval.id == ApprovalStep.approval_id)
                       .where(ApprovalStep.status == "pending", ApprovalStep.assigned_to_id == user.sub, Approval.status == "pending"))
    since = utcnow() - timedelta(days=30)
    decided_by_me = _count(db, select(ApprovalStep.id).where(ApprovalStep.decided_by_id == user.sub, ApprovalStep.decided_at >= since))
    recent = db.scalars(select(Approval).where(Approval.decided_at >= since, Approval.status.in_(("approved", "rejected")))).all()
    approved = [a for a in recent if a.status == "approved"]
    value: dict[str, Decimal] = {}
    for a in approved:
        value[a.currency] = value.get(a.currency, Decimal("0")) + a.total_amount
    hours = [(a.decided_at - a.created_at).total_seconds() / 3600 for a in recent if a.decided_at]
    today = utcnow()
    months, y, m = [], today.year, today.month
    for _ in range(6):
        months.append(f"{y:04d}-{m:02d}")
        m -= 1
        if m == 0:
            y, m = y - 1, 12
    months.reverse()
    per = dict.fromkeys(months, 0)
    first = datetime(int(months[0][:4]), int(months[0][5:]), 1)
    for (decided,) in db.execute(select(Approval.decided_at).where(Approval.decided_at >= first, Approval.status.in_(("approved", "rejected")))):
        key = f"{decided.year:04d}-{decided.month:02d}"
        if key in per:
            per[key] += 1
    return dict(waiting_for_me=waiting, overdue_for_me=overdue, delegated_to_me=delegated, decided_by_me_30d=decided_by_me, approved_30d=len(approved),
                rejected_30d=len(recent) - len(approved), approved_value_30d={k: v.quantize(Decimal("0.01")) for k, v in value.items()},
                avg_decision_hours_30d=round(sum(hours) / len(hours), 1) if hours else None, monthly=list(per.items()))
