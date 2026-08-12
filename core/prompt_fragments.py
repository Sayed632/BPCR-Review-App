"""
core/prompt_fragments.py
Shared instruction blocks reused across every extraction prompt
(master spec parsing + executed page extraction), so scientific
notation and chemical naming are handled consistently everywhere
instead of drifting between prompts.
"""

SCIENTIFIC_NOTATION_INSTRUCTIONS = (
    "This document may contain pharmaceutical/chemical scientific notation. "
    "Handle it precisely:\n"
    "- Chemical names, including full IUPAC names (which can be long, "
    "hyphenated, and contain locants/stereodescriptors like '(2S,3R)-', "
    "'(E)-', '(Z)-', multiplying prefixes like 'di-', 'tri-', and bracketed "
    "substituent groups), must be transcribed EXACTLY as printed/written - "
    "do not shorten, simplify, translate to a common/trade name, or guess "
    "spelling of any part of the name.\n"
    "- Preserve special symbols exactly: degree symbol (°C, °F), plus-minus "
    "(±), micro (µ or μ), Greek letters (α, β, γ, Δ), subscripts/superscripts "
    "(e.g. H₂O, cm², 10⁻³), arrows (→), and percent (%).\n"
    "- Preserve units and their case exactly (e.g. 'mL' vs 'ml' vs 'ML' can "
    "matter) - do not normalize or 'correct' them.\n"
    "- If a value uses ± notation for a tolerance (e.g. '87±2°C'), keep that "
    "notation when transcribing the raw written value, but see the specific "
    "instructions elsewhere for how to convert it into spec_min/spec_max "
    "numbers where that applies."
)
