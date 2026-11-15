"""RFQ/Quotation service -> purchase order service (Phase 7). When procurement awards an RFQ, the award can be read here.
`GET /internal/v1/rfqs/{rfq_id}/award` returns this, or 404 while there is no active award (never awarded, or the award was revoked).
Amounts are exact decimals; `unit_price` has up to 4 decimals, `line_total` and `total_amount` are rounded half up to 2."""
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field

CONTRACT_VERSION = 1


class AwardItem(BaseModel):
    line_no: int
    rfq_item_id: str
    description: str
    specification: str | None = None
    quantity: Decimal
    unit: str
    unit_price: Decimal | None  # null only when the award was made with the missing-items acknowledgement
    line_total: Decimal | None


class AwardRef(BaseModel):
    contract_version: int = CONTRACT_VERSION
    selection_id: str
    rfq_id: str
    rfq_number: str
    rfq_title: str
    purchase_request_id: str
    purchase_request_number: str
    needed_by: date | None = None
    vendor_id: str
    vendor_number: str
    vendor_name: str
    quotation_id: str
    quotation_number: str
    currency: str
    total_amount: Decimal
    lead_time_days: int
    valid_until: date
    payment_terms_days: int | None = None
    terms: str = ""
    items: list[AwardItem] = Field(default_factory=list)
    acknowledged_missing_items: bool = False
    justification: str
    selected_by_name: str
    selected_at: datetime
