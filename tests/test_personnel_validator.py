from core.personnel_validator import validate_operator, validate_operations

PERSONNEL = [
    {"emp_id": "E001", "name": "A. Kumar", "designation": "Chemist"},
    {"emp_id": "E002", "name": "B. Rao", "designation": "Supervisor"},
]


def test_exact_match():
    result = validate_operator("A. Kumar", PERSONNEL)
    assert result["status"] == "MATCHED"


def test_fuzzy_match_minor_variance():
    result = validate_operator("A Kumar", PERSONNEL)  # missing period
    assert result["status"] in ("MATCHED", "FUZZY_MATCHED")


def test_unrecognized_name():
    result = validate_operator("Z. Stranger", PERSONNEL)
    assert result["status"] == "UNRECOGNIZED"


def test_missing_operator():
    result = validate_operator("BLANK", PERSONNEL)
    assert result["status"] == "MISSING"


def test_validate_operations_batch():
    ops = [
        {"operation_id": "OP-01", "page_no": 1, "operator": "A. Kumar"},
        {"operation_id": "OP-02", "page_no": 1, "operator": "Nobody Real"},
    ]
    results = validate_operations(ops, PERSONNEL)
    assert results[0]["status"] == "MATCHED"
    assert results[1]["status"] == "UNRECOGNIZED"
