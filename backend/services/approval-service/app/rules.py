from decimal import Decimal

MAX_LEVELS = 3


def levels_for(total: Decimal, currency: str, thresholds: dict[str, list[Decimal]]) -> int:
    """How many different managers must approve. A currency with no thresholds gets the strictest route."""
    t = thresholds.get(currency)
    if t is None:
        return MAX_LEVELS
    return 1 + sum(1 for limit in t if total >= limit)
