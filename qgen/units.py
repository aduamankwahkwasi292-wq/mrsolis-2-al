"""
Units are the backbone of the whole math engine: they're what let us (a)
find numeric "givens" in a sentence, (b) name the unknown quantity when a
question says "find the current" with no unit attached, and (c) pick the
right formula out of the library by matching the SET of quantities involved.

Matching is deliberately two-phase - find a "number + trailing letters/
symbol" token first, then resolve that token separately - rather than
encoding prefix/case rules directly into one regex. A single regex trying
to do both made "kg" ambiguous between the unit "kg" and prefix "k" + unit
"g", and case-sensitive-only matching missed "kOhm" (vs "kohm"/"kΩ").
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Optional, Tuple

# Case-SENSITIVE symbol units. SI convention distinguishes case (V vs v),
# and single-letter symbols are too collision-prone to match loosely.
SYMBOL_UNITS = {
    "V": "voltage", "A": "current", "W": "power", "Ω": "resistance",
    "F": "capacitance", "H": "inductance", "Hz": "frequency",
    "N": "force", "J": "energy", "Pa": "pressure", "K": "temperature",
    "m": "length", "cm": "length", "mm": "length", "km": "length",
    "kg": "mass", "g": "mass", "s": "time", "rad": "angle", "%": "percent",
    "m/s": "speed", "km/h": "speed", "mph": "speed",
    "m/s^2": "acceleration", "m/s2": "acceleration",
    "m^2": "area", "m2": "area", "cm^2": "area", "cm2": "area",
    "m^3": "volume", "m3": "volume", "cm^3": "volume", "cm3": "volume",
    "°C": "temperature", "°": "angle", "C": "charge",
}

# Unit suffixes are ambiguous for several quantities (radius/diameter/
# height/wavelength are all just "a length"). If one of these context
# words appears shortly before the matched number, it overrides the
# generic unit-based tag - this only kicks in for the generic "length"/
# "time" tags, never overriding an already-specific unit like m/s.
_CONTEXT_OVERRIDE_WORDS = {
    "radius": "radius", "diameter": "diameter", "wavelength": "wavelength",
    "height": "length", "width": "length", "depth": "length", "distance": "length",
}
_OVERRIDABLE_QUANTITIES = {"length"}
# Which of the above may take an SI prefix glued directly on (kV, mA, µF...).
# Deliberately excludes multi-char/composite ones (kg, cm, m/s^2, ...) since
# those are already complete symbols in the table above.
PREFIXABLE_BASE = {"V", "A", "W", "Ω", "F", "H", "Hz", "N", "J", "Pa", "s", "m", "g"}
PREFIXES = {"p": 1e-12, "n": 1e-9, "µ": 1e-6, "u": 1e-6, "m": 1e-3, "c": 1e-2,
            "k": 1e3, "M": 1e6, "G": 1e9}

# Case-INSENSITIVE word units - people write "Ohm", "ohm", "OHMS" all sorts
# of ways, unlike single-letter symbols.
WORD_UNITS = {
    "volt": "voltage", "volts": "voltage",
    "amp": "current", "amps": "current", "ampere": "current", "amperes": "current",
    "watt": "power", "watts": "power",
    "ohm": "resistance", "ohms": "resistance",
    "farad": "capacitance", "farads": "capacitance",
    "henry": "inductance",
    "hertz": "frequency",
    "newton": "force", "newtons": "force",
    "joule": "energy", "joules": "energy",
    "pascal": "pressure", "pascals": "pressure",
    "meter": "length", "meters": "length", "metre": "length", "metres": "length",
    "gram": "mass", "grams": "mass", "kilogram": "mass", "kilograms": "mass",
    "second": "time", "seconds": "time", "sec": "time",
    "minute": "time", "minutes": "time", "min": "time",
    "hour": "time", "hours": "time", "hr": "time",
    "degree": "angle", "degrees": "angle", "radian": "angle", "radians": "angle",
}

QUANTITY_NAME_WORDS = {
    "voltage": "voltage", "volts": "voltage", "volt": "voltage", "emf": "voltage",
    "current": "current", "amperage": "current",
    "power": "power", "wattage": "power",
    "resistance": "resistance", "capacitance": "capacitance", "inductance": "inductance",
    "frequency": "frequency", "period": "time", "time": "time", "duration": "time",
    "length": "length", "distance": "length", "height": "length", "width": "length",
    "radius": "radius", "diameter": "diameter",
    "mass": "mass", "weight": "mass", "force": "force", "pressure": "pressure",
    "energy": "energy", "speed": "speed", "velocity": "speed", "acceleration": "acceleration",
    "angle": "angle", "temperature": "temperature", "area": "area", "volume": "volume",
    "circumference": "circumference", "efficiency": "percent",
    "momentum": "momentum", "work": "work", "torque": "torque",
    "density": "density", "wavelength": "wavelength", "charge": "charge",
    "impulse": "momentum",
}

_TOKEN_RE = re.compile(r"(\d[\d,]*\.?\d*)\s*([A-Za-zµ°Ω%/^0-9]{1,7})(?![A-Za-z])")


def resolve_unit(token: str) -> Optional[Tuple[str, float]]:
    """token -> (quantity_name, multiplier_to_base) or None."""
    if token in SYMBOL_UNITS:
        return SYMBOL_UNITS[token], 1.0
    low = token.lower()
    if low in WORD_UNITS:
        return WORD_UNITS[low], 1.0
    if len(token) >= 2 and token[0] in PREFIXES and token[1:] in SYMBOL_UNITS \
            and token[1:] in PREFIXABLE_BASE:
        return SYMBOL_UNITS[token[1:]], PREFIXES[token[0]]
    if len(token) >= 2 and token[0] in PREFIXES and token[1:].lower() in WORD_UNITS:
        return WORD_UNITS[token[1:].lower()], PREFIXES[token[0]]
    return None


@dataclass
class Quantity:
    value: float
    unit_symbol: str
    quantity_name: str
    base_value: float
    start: int
    end: int
    raw: str


def find_quantities(text: str) -> List[Quantity]:
    out = []
    for m in _TOKEN_RE.finditer(text):
        num_str, unit_tok = m.group(1), m.group(2)
        resolved = resolve_unit(unit_tok)
        if resolved is None:
            continue
        qname, mult = resolved
        try:
            value = float(num_str.replace(",", ""))
        except ValueError:
            continue
        if qname in _OVERRIDABLE_QUANTITIES:
            window = text[max(0, m.start() - 24): m.start()].lower()
            for word, override in _CONTEXT_OVERRIDE_WORDS.items():
                if re.search(rf"\b{word}\b", window):
                    qname = override
                    break
        out.append(Quantity(
            value=value, unit_symbol=unit_tok, quantity_name=qname,
            base_value=value * mult, start=m.start(), end=m.end(), raw=m.group(0),
        ))
    return out


def quantity_name_from_word(word: str) -> Optional[str]:
    return QUANTITY_NAME_WORDS.get(word.lower().strip())
