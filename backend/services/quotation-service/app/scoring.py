"""Supplier scoring. Pure functions, no database, no clock: the same quotations and the same judgements always give the same numbers.

Criteria and weights (they add up to 100):
  price       40  calculated: 100 x (lowest total in the same currency / this total)
  delivery    20  calculated: 100 x (shortest lead time in the same currency / this lead time)
  compliance  25  entered by the evaluator, 0 to 10, counted as 0 to 100
  terms       15  entered by the evaluator, 0 to 10, counted as 0 to 100

Rules:
  * Only complete quotations (every RFQ line priced) are scored. A partial quotation cannot be compared on price fairly, so it gets no calculated scores.
  * Quotations are only compared with others in the same currency. There is no currency conversion.
  * The overall score exists only when all four parts exist; until the evaluator has entered both judgements it is missing, not guessed.
  * Eligibility is not a score: the vendor must be verified at the moment of selection (checked by the selection, not here).
  * Scores are rounded half up to 2 decimals. Ties are ordered by lower total, then earlier submission.
"""
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal

WEIGHTS: dict[str, int] = {"price": 40, "delivery": 20, "compliance": 25, "terms": 15}
HUNDRED = Decimal(100)
TWO = Decimal("0.01")


@dataclass
class Candidate:
    key: str
    currency: str
    total: Decimal
    lead_time_days: int | None
    complete: bool
    compliance_score: int | None = None  # 0 to 10
    terms_score: int | None = None  # 0 to 10
    submitted_order: int = 0  # tie-break: lower is earlier


@dataclass
class Scored:
    key: str
    price: Decimal | None = None
    delivery: Decimal | None = None
    compliance: Decimal | None = None
    terms: Decimal | None = None
    total: Decimal | None = None
    missing: list[str] = field(default_factory=list)
    lowest_price: bool = False
    fastest: bool = False
    rank: int | None = None


def _q(v: Decimal) -> Decimal:
    return v.quantize(TWO, rounding=ROUND_HALF_UP)


def _ratio_score(best: Decimal, value: Decimal) -> Decimal:
    """100 for the best value, less for worse ones. If the best is 0 (everything free) a 0 scores 100 and anything else 0."""
    if value == 0:
        return HUNDRED
    return _q(HUNDRED * best / value)


def score(candidates: list[Candidate]) -> dict[str, Scored]:
    out: dict[str, Scored] = {c.key: Scored(c.key) for c in candidates}
    for c in candidates:
        s = out[c.key]
        if c.compliance_score is not None:
            s.compliance = _q(Decimal(c.compliance_score) * 10)
        if c.terms_score is not None:
            s.terms = _q(Decimal(c.terms_score) * 10)
        if not c.complete:
            s.missing.append("Some items are not quoted")
    for currency in {c.currency for c in candidates}:
        group = [c for c in candidates if c.currency == currency and c.complete and c.lead_time_days]
        if not group:
            continue
        cheapest = min(c.total for c in group)
        quickest = min(c.lead_time_days for c in group if c.lead_time_days)
        for c in group:
            s = out[c.key]
            s.price = _ratio_score(cheapest, c.total)
            s.delivery = _ratio_score(Decimal(quickest), Decimal(c.lead_time_days or 0))
            s.lowest_price = c.total == cheapest
            s.fastest = c.lead_time_days == quickest
    for c in candidates:
        s = out[c.key]
        parts = {"price": s.price, "delivery": s.delivery, "compliance": s.compliance, "terms": s.terms}
        s.missing += [f"{name} score" for name, v in parts.items() if v is None and c.complete and name in ("compliance", "terms")]
        if all(v is not None for v in parts.values()):
            s.total = _q(sum((Decimal(WEIGHTS[k]) * v for k, v in parts.items()), Decimal(0)) / HUNDRED)  # type: ignore[operator]
    for currency in {c.currency for c in candidates}:
        ranked = sorted((c for c in candidates if c.currency == currency and out[c.key].total is not None),
                        key=lambda c: (-(out[c.key].total or Decimal(0)), c.total, c.submitted_order))
        for n, c in enumerate(ranked, start=1):
            out[c.key].rank = n
    return out
