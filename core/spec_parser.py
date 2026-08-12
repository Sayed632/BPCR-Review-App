"""
core/spec_parser.py
Parses a Master BPCR (printed template, not handwritten) into the same
JSON spec schema used elsewhere in this app (see
data/master_specs/apple_orange_batch.json for the reference shape).

Each page is sent to the vision model independently (a Master BPCR can
run many pages), then the per-page fragments are merged into one
consolidated spec. This always needs a human review pass afterwards
(see ui/master_spec_view.py) - treat this as a first draft, not a
final answer, since a misread spec (e.g. a swapped tolerance number)
is worse than a misread executed value.
"""

import json
from core.model_router import extract_field
from core.prompt_fragments import SCIENTIFIC_NOTATION_INSTRUCTIONS

REQUIRED_TOP_LEVEL_KEYS = ["product_name", "bpcr_version", "personnel", "materials", "operations"]


def _build_master_bpcr_prompt(page_number: int) -> str:
    return (
        "This image is one page from a MASTER (blank/template) batch "
        "production control record for a pharmaceutical product - NOT a "
        "filled-in executed record. Extract the printed structure/spec "
        "information visible on this page only. This is page "
        f"{page_number} of a multi-page document, so many sections will "
        "be empty on any given page - that's expected, just leave those "
        "as empty arrays/null.\n\n"
        f"{SCIENTIFIC_NOTATION_INSTRUCTIONS}\n\n"
        "Extract into exactly this JSON shape:\n"
        "{\n"
        '  "product_name": "<string or null if not on this page>",\n'
        '  "bpcr_version": "<string or null if not on this page>",\n'
        '  "personnel": [{"emp_id": "<string>", "name": "<string>", '
        '"designation": "<string>"}],\n'
        '  "materials": [{"material": "<name>", "type": "<e.g. KSM/GRM>", '
        '"code": "<string>", "qty_indented": <number>, "unit": "<e.g. kg, L>", '
        '"tolerance_pct": <number>, "tolerance_type": "two_sided"}],\n'
        '  "operations": [{\n'
        '    "operation_id": "<use the number printed on the page, e.g. '
        '\'1\' -> \'OP-01\', \'IPC-1\' stays \'IPC-1\'>",\n'
        '    "description": "<short description of what this step does>",\n'
        '    "requires_operator": <true/false - does this step have a '
        'sign/initial column>,\n'
        '    "requires_start_time": <true/false - does it have a start '
        'time/date field>,\n'
        '    "requires_end_time": <true/false - does it have an end '
        'time/date field>,\n'
        '    "materials_used": [{"material": "<name>", "unit": "<unit>"}],\n'
        '    "parameters": [{"parameter": "<name, e.g. Reflux Temperature>", '
        '"unit": "<e.g. degC>", "expected_type": "numeric or text", '
        '"spec_min": <number or null>, "spec_max": <number or null>}],\n'
        '    "time_series_log": null or {"table_name": "<e.g. Table-1>", '
        '"interval_minutes": <number>, "interval_tolerance_minutes": <number>, '
        '"value_unit": "<unit>", "spec_min": <number>, "spec_max": <number>},\n'
        '    "ipc": null or {"ipc_name": "<e.g. IPC-1>", "test": "<what is '
        'tested>", "spec_nmt_pct": <number, if a Not-More-Than % spec>, '
        '"conditional_action": "<plain text description of the branch '
        'logic if the result fails spec, else null>"},\n'
        '    "conditional_only": <true only if this whole step only runs '
        "when a prior IPC/condition fails, else false>\n"
        "  }]\n"
        "}\n\n"
        "Rules:\n"
        "- Only include personnel/materials/operations actually visible on "
        "THIS page. Leave arrays empty if this page has none.\n"
        "- Do not invent spec_min/spec_max values - only extract numbers "
        "that are actually printed. Use null if not specified.\n"
        "- IMPORTANT: many specs are printed as a nominal value plus a "
        "tolerance using a ± symbol, e.g. 'RPM 10±5' or '87±2°C'. When you "
        "see this notation, you MUST convert it into a proper range: "
        "spec_min = nominal - tolerance, spec_max = nominal + tolerance. "
        "For 'RPM 10±5' that means spec_min=5 and spec_max=15 - NOT "
        "spec_min=10 and spec_max=10. Never repeat the nominal value for "
        "both spec_min and spec_max unless the printed spec truly has zero "
        "tolerance.\n"
        "- If a spec is printed as an explicit range already (e.g. "
        "'85-90 degC'), use those two numbers directly as spec_min/spec_max.\n"
        "- Respond with ONLY the raw JSON object above, filled in. No "
        "markdown code fences, no explanation text, no extra commentary."
    )


def parse_master_bpcr_page(image_bytes: bytes, page_number: int) -> dict:
    """
    Returns a spec fragment dict for one page, or a fragment with
    "_error" set if the call/parse failed (caller decides whether to
    surface that to the user - a failed page shouldn't silently drop
    data, since a missed operation on a bad page is a real gap).
    """
    prompt = _build_master_bpcr_prompt(page_number)
    result = extract_field(prompt, image_bytes)

    empty_fragment = {
        "product_name": None,
        "bpcr_version": None,
        "personnel": [],
        "materials": [],
        "operations": [],
        "_page_number": page_number,
        "_error": None,
    }

    if not result["success"]:
        empty_fragment["_error"] = result.get("error") or "Extraction call failed for this page."
        return empty_fragment

    raw_text = result["text"].strip()
    if raw_text.startswith("```"):
        raw_text = raw_text.strip("`").replace("json", "", 1).strip()

    try:
        parsed = json.loads(raw_text)
    except json.JSONDecodeError:
        empty_fragment["_error"] = f"Could not parse model JSON response: {raw_text[:300]}"
        return empty_fragment

    for key in REQUIRED_TOP_LEVEL_KEYS:
        parsed.setdefault(key, [] if key in ("personnel", "materials", "operations") else None)

    # Trust the real page index over anything the model guesses, and
    # tag every operation extracted from this page with it - this is
    # used later by app.py to route executed-page images against the
    # right subset of operations.
    for op in parsed["operations"]:
        op["page_no"] = page_number

    parsed["_page_number"] = page_number
    parsed["_error"] = None
    return parsed


def merge_spec_fragments(fragments: list[dict]) -> dict:
    """
    Consolidates per-page fragments (from parse_master_bpcr_page) into
    one spec dict matching the app's schema. Any page-level errors are
    collected under "_page_errors" so the review UI can flag exactly
    which pages need a manual look, rather than silently dropping them.
    """
    product_name = None
    bpcr_version = None
    personnel_by_id: dict[str, dict] = {}
    materials_by_name: dict[str, dict] = {}
    operations_by_id: dict[str, dict] = {}
    page_errors = []

    for frag in fragments:
        if frag.get("_error"):
            page_errors.append({"page": frag.get("_page_number"), "error": frag["_error"]})
            continue

        if not product_name and frag.get("product_name"):
            product_name = frag["product_name"]
        if not bpcr_version and frag.get("bpcr_version"):
            bpcr_version = frag["bpcr_version"]

        for person in frag.get("personnel") or []:
            key = person.get("emp_id") or person.get("name")
            if key and key not in personnel_by_id:
                personnel_by_id[key] = person

        for mat in frag.get("materials") or []:
            key = (mat.get("material") or "").strip().lower()
            if not key:
                continue
            if key not in materials_by_name:
                materials_by_name[key] = mat
            else:
                # fill in any fields the first occurrence was missing
                for k, v in mat.items():
                    if materials_by_name[key].get(k) in (None, "") and v not in (None, ""):
                        materials_by_name[key][k] = v

        for op in frag.get("operations") or []:
            op_id = op.get("operation_id")
            if not op_id:
                continue
            if op_id not in operations_by_id:
                operations_by_id[op_id] = op
            else:
                # merge materials/parameters lists rather than overwrite,
                # in case the same operation's fields were split oddly
                # across a page boundary
                existing = operations_by_id[op_id]
                existing.setdefault("materials_used", [])
                existing.setdefault("parameters", [])
                seen_mats = {m.get("material") for m in existing["materials_used"]}
                for m in op.get("materials_used", []):
                    if m.get("material") not in seen_mats:
                        existing["materials_used"].append(m)
                seen_params = {p.get("parameter") for p in existing["parameters"]}
                for p in op.get("parameters", []):
                    if p.get("parameter") not in seen_params:
                        existing["parameters"].append(p)

    operations = sorted(
        operations_by_id.values(),
        key=lambda o: (o.get("page_no") or 0, str(o.get("operation_id"))),
    )

    return {
        "product_name": product_name or "Unnamed Product (edit me)",
        "bpcr_version": bpcr_version or "v1.0",
        "personnel": list(personnel_by_id.values()),
        "materials": list(materials_by_name.values()),
        "operations": operations,
        "_page_errors": page_errors,
    }


def parse_master_bpcr(page_images: list[bytes]) -> dict:
    """Convenience wrapper: parse every page then merge into one spec."""
    fragments = [parse_master_bpcr_page(img, i + 1) for i, img in enumerate(page_images)]
    return merge_spec_fragments(fragments)


def validate_spec(spec: dict) -> list[str]:
    """Returns a list of human-readable problems, empty if the spec is usable."""
    problems = []
    if not spec.get("operations"):
        problems.append("No operations were extracted - this spec can't be used to review pages yet.")
    for i, op in enumerate(spec.get("operations", [])):
        if not op.get("operation_id"):
            problems.append(f"Operation at index {i} is missing an operation_id.")
        if not op.get("description"):
            problems.append(f"Operation {op.get('operation_id', i)} is missing a description.")
    seen_ids = set()
    for op in spec.get("operations", []):
        oid = op.get("operation_id")
        if oid in seen_ids:
            problems.append(f"Duplicate operation_id '{oid}' - merge or rename one of them.")
        seen_ids.add(oid)
    return problems
