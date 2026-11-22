import math

from quant_agent_mcp.evals import CASES, answer_contains, score_case

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