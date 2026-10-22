"""Display marks without insignificant zeros; never use this for calculations or IDs."""
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP, localcontext


def compact_number(value):
    if value is None or value == "":
        return ""
    try:
        number = Decimal(str(value))
        if not number.is_finite():
            return str(value)
        with localcontext() as context:
            context.prec = max(28, len(number.as_tuple().digits) + abs(number.adjusted()) + 4)
            number = number.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        return format(number, "f").rstrip("0").rstrip(".") if number else "0"
    except (InvalidOperation, ValueError, TypeError):
        return str(value)
