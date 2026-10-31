"""Half-up rounding and Indian-style formatting (all money maths goes through here)."""
from decimal import ROUND_HALF_UP, Decimal


def d(x) -> Decimal:
    return Decimal(str(x or 0))


def money(x) -> float:
    return float(d(x).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def pct(x) -> float:
    return float(d(x).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP))


def change_pct(current, previous) -> float | None:
    if current is None or previous in (None, 0):
        return None
    return pct((d(current) - d(previous)) / d(previous) * 100)


def inr(x, decimals: bool = False) -> str:
    """₹1,05,800 style. decimals=True keeps paise."""
    value = money(x)
    neg = value < 0
    whole, frac = f"{abs(value):.2f}".split(".")
    if len(whole) > 3:
        head, tail = whole[:-3], whole[-3:]
        groups = []
        while len(head) > 2:
            groups.insert(0, head[-2:])
            head = head[:-2]
        if head:
            groups.insert(0, head)
        whole = ",".join(groups + [tail])
    s = f"₹{whole}" + (f".{frac}" if decimals else "")
    return f"-{s}" if neg else s
