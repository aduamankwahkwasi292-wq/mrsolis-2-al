"""Turn a Variation back into question text. Two paths:
- Same unknown as the original: substitute new numbers directly into the
  ORIGINAL sentence at their original character positions - zero grammar
  risk, since we never touch syntax, only numeric literals.
- Different unknown: original given-clauses are reused verbatim (still
  zero risk) except the one whose role flipped, which needs a small
  per-quantity template. Far narrower surface than free-form transformation.
"""
from __future__ import annotations

from typing import Optional

from .paramgen import Variation
from .wordproblems import WordProblem

QUANTITY_TEMPLATES = {
    "voltage": {"given": "the voltage is {v}", "ask": "the voltage"},
    "current": {"given": "the current is {v}", "ask": "the current"},
    "power": {"given": "it consumes {v} of power", "ask": "the power"},
    "resistance": {"given": "the resistance is {v}", "ask": "the resistance"},
    "capacitance": {"given": "the capacitance is {v}", "ask": "the capacitance"},
    "inductance": {"given": "the inductance is {v}", "ask": "the inductance"},
    "frequency": {"given": "the frequency is {v}", "ask": "the frequency"},
    "time": {"given": "the time taken is {v}", "ask": "the time taken"},
    "length": {"given": "the distance covered is {v}", "ask": "the distance"},
    "radius": {"given": "the radius is {v}", "ask": "the radius"},
    "diameter": {"given": "the diameter is {v}", "ask": "the diameter"},
    "area": {"given": "the area is {v}", "ask": "the area"},
    "circumference": {"given": "the circumference is {v}", "ask": "the circumference"},
    "mass": {"given": "the mass is {v}", "ask": "the mass"},
    "force": {"given": "a force of {v} is applied", "ask": "the force"},
    "acceleration": {"given": "the acceleration is {v}", "ask": "the acceleration"},
    "speed": {"given": "the speed is {v}", "ask": "the speed"},
    "energy": {"given": "the energy is {v}", "ask": "the energy"},
    "pressure": {"given": "the pressure is {v}", "ask": "the pressure"},
    "momentum": {"given": "the momentum is {v}", "ask": "the momentum"},
    "work": {"given": "the work done is {v}", "ask": "the work done"},
    "torque": {"given": "the torque is {v}", "ask": "the torque"},
    "density": {"given": "the density is {v}", "ask": "the density"},
    "wavelength": {"given": "the wavelength is {v}", "ask": "the wavelength"},
    "charge": {"given": "the charge is {v}", "ask": "the charge"},
    "volume": {"given": "the volume is {v}", "ask": "the volume"},
}

DEFAULT_UNIT_FOR_QUANTITY = {
    "voltage": "V", "current": "A", "power": "W", "resistance": "ohm",
    "capacitance": "F", "inductance": "H", "frequency": "Hz", "time": "s",
    "length": "m", "radius": "m", "diameter": "m", "area": "m^2",
    "circumference": "m", "mass": "kg", "force": "N", "acceleration": "m/s^2",
    "speed": "m/s", "energy": "J", "pressure": "Pa", "momentum": "kg*m/s",
    "work": "J", "torque": "N*m", "density": "kg/m^3", "wavelength": "m",
    "charge": "C", "volume": "m^3",
}


def format_value(value: float) -> str:
    if abs(value - round(value)) < 1e-9:
        return str(int(round(value)))
    s = f"{value:.4f}".rstrip("0").rstrip(".")
    return s


def _unit_for_given(wp: WordProblem, quantity_name: str) -> str:
    for g in wp.givens:
        if g.quantity_name == quantity_name:
            return g.unit_symbol
    return DEFAULT_UNIT_FOR_QUANTITY.get(quantity_name, "")


def _rescale_to_display(wp: WordProblem, quantity_name: str, new_base_value: float) -> float:
    """A given originally written as '1.5kOhm' has base_value=1500. If the
    new base value is 3000, we want to display '3kOhm', not '3000kOhm' -
    rescale by the same implied prefix factor the original used."""
    for g in wp.givens:
        if g.quantity_name == quantity_name and g.value:
            factor = g.base_value / g.value
            return new_base_value / factor
    return new_base_value


def render_same_unknown(wp: WordProblem, variation: Variation) -> str:
    text = wp.sentence
    replacements = []
    for g in wp.givens:
        if g.quantity_name not in variation.given_values:
            continue
        new_base = variation.given_values[g.quantity_name]
        display_val = _rescale_to_display(wp, g.quantity_name, new_base)
        new_text = f"{format_value(display_val)}{g.unit_symbol}"
        replacements.append((g.start, g.end, new_text))
    for start, end, new_text in sorted(replacements, key=lambda r: -r[0]):
        text = text[:start] + new_text + text[end:]
    return text


def render_swapped_unknown(wp: WordProblem, variation: Variation) -> Optional[str]:
    scenario = wp.scenario or "the system"
    scenario_lower = scenario[0].lower() + scenario[1:] if scenario else scenario
    given_phrases = []
    for qname, base_val in sorted(variation.given_values.items()):
        tmpl = QUANTITY_TEMPLATES.get(qname)
        if tmpl is None:
            return None
        display_val = _rescale_to_display(wp, qname, base_val) if qname != wp.ask_quantity else base_val
        unit = _unit_for_given(wp, qname)
        val_str = f"{format_value(display_val)}{unit}"
        given_phrases.append(tmpl["given"].format(v=val_str))

    ask_tmpl = QUANTITY_TEMPLATES.get(variation.unknown)
    if ask_tmpl is None:
        return None

    if len(given_phrases) == 1:
        given_clause = given_phrases[0]
    else:
        given_clause = ", ".join(given_phrases[:-1]) + ", and " + given_phrases[-1]

    prefix = f"For {scenario_lower}, " if scenario else ""
    given_clause = given_clause[0].upper() + given_clause[1:] if not prefix else given_clause
    sentence = f"{prefix}{given_clause}. Calculate {ask_tmpl['ask']}."
    return sentence


def render_question(wp: WordProblem, variation: Variation) -> Optional[str]:
    if variation.unknown == wp.ask_quantity:
        return render_same_unknown(wp, variation)
    return render_swapped_unknown(wp, variation)
