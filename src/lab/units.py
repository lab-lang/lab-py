"""Public quantities; recorded plans use Decimal microlitres and seconds."""

from decimal import Decimal
from typing import Any

import pint

units = pint.UnitRegistry(non_int_type=Decimal)
uL = units.microliter
mL = units.milliliter
seconds = units.second
minutes = units.minute
Quantity = pint.Quantity


def celsius(value: int | float | str | Decimal) -> pint.Quantity:
    """An absolute Celsius temperature; avoids multiplying an offset unit."""
    if isinstance(value, bool):
        raise TypeError("A temperature must be numeric")
    return units.Quantity(Decimal(str(value)), units.degC)


def temperature(value: Any) -> Decimal:
    """Normalize an absolute temperature to Celsius, including negative values."""
    return magnitude(value, "kelvin", positive=False) - Decimal("273.15")


def magnitude(value: Any, unit: str, *, positive: bool = True) -> Decimal:
    """Normalize the decimal spelling of a quantity, rejecting unitless input."""
    if not isinstance(value, pint.Quantity) or isinstance(value.magnitude, bool):
        raise TypeError(f"Expected a quantity compatible with {unit}")
    try:
        # Normalize floats before conversion rather than expanding their binary representation.
        quantity = units.Quantity(Decimal(str(value.magnitude)), str(value.units))
        result = Decimal(str(quantity.to(unit).magnitude))
    except (ValueError, ArithmeticError, pint.PintError) as exc:
        raise ValueError(f"Expected a finite quantity compatible with {unit}") from exc
    if not result.is_finite() or result < 0 or (positive and result == 0):
        raise ValueError(f"Expected a {'positive' if positive else 'nonnegative'} finite {unit}")
    return result


def number(value: Decimal) -> str:
    """Canonical decimal text without exponent notation or insignificant zeros."""
    text = format(value, "f")
    return text.rstrip("0").rstrip(".") if "." in text else text
