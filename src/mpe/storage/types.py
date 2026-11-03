"""Column types that keep SQLite honest.

``DecimalText`` stores :class:`~decimal.Decimal` as canonical TEXT (TEXT affinity, so SQLite never
converts it to a binary float). ``UTCText`` stores aware datetimes as ``YYYY-MM-DDTHH:MM:SSZ``.
"""

from __future__ import annotations

import math
from datetime import datetime
from decimal import Decimal, InvalidOperation

from sqlalchemy import Text
from sqlalchemy.types import TypeDecorator

from mpe.clock import from_iso, to_iso


def to_decimal(value: object) -> Decimal | None:
    """Convert provider numbers to Decimal via ``str`` so floats keep their shortest repr."""
    if value is None:
        return None
    if isinstance(value, Decimal):
        d = value
    elif isinstance(value, float):  # includes numpy.float64
        value = float(value)
        if not math.isfinite(value):
            return None
        d = Decimal(repr(value))
    else:
        if hasattr(value, "item"):  # other numpy scalars
            value = value.item()
            if isinstance(value, float):
                return to_decimal(value)
        try:
            d = Decimal(str(value).strip())
        except InvalidOperation as e:
            raise ValueError(f"not a decimal: {value!r}") from e
    if not d.is_finite():
        return None
    return d


def canonical(d: Decimal) -> str:
    """Plain (non-exponent) text with trailing zeros removed: ``Decimal('1.50')`` -> ``'1.5'``."""
    if d == 0:
        return "0"
    t = format(d.normalize(), "f")
    return t


class DecimalText(TypeDecorator):
    impl = Text
    cache_ok = True

    def process_bind_param(self, value, dialect):
        d = to_decimal(value)
        return None if d is None else canonical(d)

    def process_result_value(self, value, dialect):
        return None if value is None else Decimal(value)


class UTCText(TypeDecorator):
    impl = Text
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if isinstance(value, str):
            value = from_iso(value)
        if not isinstance(value, datetime):
            raise TypeError(f"expected datetime, got {type(value).__name__}")
        return to_iso(value)

    def process_result_value(self, value, dialect):
        return None if value is None else from_iso(value)
