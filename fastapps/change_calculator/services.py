from decimal import Decimal

from reports.currency import get_rate


def convert(amount, from_currency, to_currency):
    """Convert with the latest rate. Raises ValueError (MissingRate) when no rate is available."""
    return Decimal(amount) * get_rate(from_currency, to_currency)
