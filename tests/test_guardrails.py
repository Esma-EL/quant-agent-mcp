import json

from quant_agent_mcp.guardrails import extract_numbers, validate_answer, write_audit

QUESTION = "Price a 1-year ATM call, spot 100, vol 20%, rate 5%"
TRACE = [
    {
        "tool": "price_option",
        "input": {"S": 100, "K": 100, "T": 1, "r": 0.05, "sigma": 0.2},
        "output": json.dumps({"price": 10.450583572185565, "delta": 0.6368306511756191}),
        "is_error": False,
    }
]


def test_extract_numbers():
    assert extract_numbers("spot 1,000.50 and vol 20%") == [(1000.5, 2, False), (20.0, 0, True)]


def test_numbers_from_tools_pass():
    out = validate_answer(QUESTION, "The call is worth 10.45 with a delta of 0.6368.", TRACE)
    assert out == {"ok": True, "unsupported": []}


def test_percent_formatting_is_recognised():
    assert validate_answer(QUESTION, "Delta is 63.68%.", TRACE)["ok"]


def test_numbers_from_question_pass():
    assert validate_answer(QUESTION, "Using spot 100, vol 20% and rate 5%.", TRACE)["ok"]


def test_invented_number_is_flagged():
    out = validate_answer(QUESTION, "The call is worth 12.30.", TRACE)
    assert not out["ok"]
    assert out["unsupported"] == ["12.3"]


def test_audit_log_appends_json_lines(tmp_path):
    path = tmp_path / "logs" / "audit.jsonl"
    write_audit({"question": "q1"}, path)
    write_audit({"question": "q2"}, path)
    lines = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    assert [entry["question"] for entry in lines] == ["q1", "q2"]
    assert "timestamp" in lines[0]




def test_unicode_minus_and_list_markers():
    assert extract_numbers("1. Delta is \u22120.5609") == [(-0.5609, 4, False)]


def test_zero_is_always_allowed():
    assert validate_answer(QUESTION, "Dividend yield q = 0.", TRACE)["ok"]