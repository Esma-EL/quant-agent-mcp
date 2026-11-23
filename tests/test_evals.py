import math

import pytest

from quant_agent_mcp.evals import CASES, answer_contains, closest_error, score_case, write_report

OK = {"ok": True, "unsupported": []}


def test_cases_are_well_formed():
    assert len({c["id"] for c in CASES}) == len(CASES)
    for case in CASES:
        for x in case.get("expect_numbers", []):
            assert math.isfinite(x)


def test_answer_contains_handles_rounding_and_percent():
    assert answer_contains("Price is 10.45.", 10.4506)
    assert answer_contains("Implied vol is 25.3%.", 0.2531)
    assert not answer_contains("Price is 11.2.", 10.4506)


def test_score_answer_case():
    case = {"id": "c", "expect_tools": ["price_option"], "expect_numbers": [10.4506]}
    out = {"answer": "It is worth 10.45.", "validation": OK,
           "tool_calls": [{"tool": "price_option", "is_error": False}]}
    assert score_case(case, out)["passed"]


def test_score_ask_case_fails_if_agent_assumes_input():
    case = {"id": "c", "expect_behaviour": "ask"}
    out = {"answer": "Assuming 20% vol, it is worth 10.45.", "validation": OK,
           "tool_calls": [{"tool": "price_option", "is_error": False}]}
    assert not score_case(case, out)["passed"]


def test_score_refuse_case():
    case = {"id": "c", "expect_behaviour": "refuse"}
    out = {"answer": "Spot must be positive.", "validation": OK,
           "tool_calls": [{"tool": "price_option", "is_error": True}]}
    assert score_case(case, out)["passed"]





def test_closest_error():
    assert closest_error("Price is 10.45.", 10.4506) == pytest.approx(0.0006)
    assert closest_error("No numbers here.", 1.0) is None


def test_report_has_summary_and_categories(tmp_path):
    rows = [
        {"id": "a", "category": "Pricing", "passed": True, "tools": ["price_option"],
         "checks": {"grounded": True, "right_tools": True}, "max_abs_error": 0.0006, "run": 1},
        {"id": "b", "category": "Safety", "passed": False, "tools": [],
         "checks": {"grounded": False}, "max_abs_error": None, "run": 1},
    ]
    assert write_report(rows, tmp_path) == 1
    report = (tmp_path / "results.md").read_text(encoding="utf-8")
    assert "Overall pass rate | 1/2 (50%)" in report
    assert "| Pricing | 1 | 1/1 (100%) | 6.0e-04 |" in report