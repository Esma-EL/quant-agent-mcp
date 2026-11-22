"""Evaluation harness: run representative trader requests through the agent and score them."""
from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path

from quant_agent_mcp.agent import MODEL, run_agent
from quant_agent_mcp.guardrails import extract_numbers
from quant_agent_mcp.pricing import bs_price, greeks, implied_vol
from quant_agent_mcp.rates import YieldCurve

CURVE = YieldCurve([1, 2, 3], [0.03, 0.034, 0.037])
CALL_1Y = greeks(100, 100, 1, 0.05, 0.2)
PUT_3M = greeks(50, 52, 0.25, 0.02, 0.3, option="put")

CASES = [
    {"id": "atm_call_price",
     "question": "Price a 1-year at-the-money European call: spot 100, strike 100, "
                 "volatility 20%, risk-free rate 5%.",
     "expect_tools": ["price_option"], "expect_numbers": [bs_price(100, 100, 1, 0.05, 0.2)]},
    {"id": "atm_put_price",
     "question": "Price a 1-year at-the-money European put: spot 100, strike 100, "
                 "volatility 20%, risk-free rate 5%.",
     "expect_tools": ["price_option"],
     "expect_numbers": [bs_price(100, 100, 1, 0.05, 0.2, option="put")]},
    {"id": "otm_call_6m",
     "question": "What is the price of a 6-month call with strike 110 on a stock trading at 100? "
                 "Volatility 25%, rate 3%.",
     "expect_tools": ["price_option"], "expect_numbers": [bs_price(100, 110, 0.5, 0.03, 0.25)]},
    {"id": "call_with_dividend",
     "question": "Price a 1-year call, spot 100, strike 95, volatility 18%, rate 4%, "
                 "dividend yield 2%.",
     "expect_tools": ["price_option"],
     "expect_numbers": [bs_price(100, 95, 1, 0.04, 0.18, q=0.02)]},
    {"id": "call_delta_gamma",
     "question": "Give me the delta and gamma of a 1-year call, spot 100, strike 100, "
                 "volatility 20%, rate 5%.",
     "expect_tools": ["option_greeks"], "expect_numbers": [CALL_1Y["delta"], CALL_1Y["gamma"]]},
    {"id": "put_price_and_delta",
     "question": "For a 3-month put with spot 50, strike 52, volatility 30% and rate 2%, "
                 "I need the price and the delta.",
     "expect_tools": ["price_option", "option_greeks"],
     "expect_numbers": [bs_price(50, 52, 0.25, 0.02, 0.3, option="put"), PUT_3M["delta"]]},
    {"id": "implied_vol_call",
     "question": "A 1-year call with spot 100 and strike 100 trades at 12.00. Rate is 5%. "
                 "What volatility does that price imply?",
     "expect_tools": ["implied_volatility"],
     "expect_numbers": [implied_vol(12.0, 100, 100, 1, 0.05)]},
    {"id": "implied_vol_put",
     "question": "A 6-month put, spot 100, strike 105, trades at 8.50 with rates at 3%. "
                 "What is its implied volatility?",
     "expect_tools": ["implied_volatility"],
     "expect_numbers": [implied_vol(8.5, 100, 105, 0.5, 0.03, option="put")]},
    {"id": "curve_discount_factor",
     "question": "Par swap rates are 3.0% (1y), 3.4% (2y) and 3.7% (3y). "
                 "What is the discount factor at 2.5 years?",
     "expect_tools": ["yield_curve"], "expect_numbers": [CURVE.discount(2.5)]},
    {"id": "curve_zero_rate",
     "question": "Using par rates of 3.0% for 1 year, 3.4% for 2 years and 3.7% for 3 years, "
                 "what is the 3-year continuously compounded zero rate?",
     "expect_tools": ["yield_curve"], "expect_numbers": [CURVE.zero_rate(3)]},
    {"id": "missing_volatility",
     "question": "Price a 1-year at-the-money call on a stock at 100 with a 5% rate.",
     "expect_behaviour": "ask"},
    {"id": "negative_spot",
     "question": "Price a 1-year call with spot -100, strike 100, volatility 20% and rate 5%.",
     "expect_behaviour": "refuse"},
    {"id": "arbitrage_price",
     "question": "A 1-year call with spot 100 and strike 100 trades at 150. "
                 "What is its implied volatility?",
     "expect_behaviour": "refuse"},
]


def answer_contains(answer, expected):
    """True if the answer shows `expected`, allowing for rounding and percent formatting."""
    for value, decimals, is_percent in extract_numbers(answer):
        candidates = [(value, decimals)]
        if is_percent:
            candidates.append((value / 100, decimals + 2))
        if any(abs(v - expected) <= 0.5 * 10**-d + 1e-12 for v, d in candidates):
            return True
    return False


def score_case(case, out):
    """Score one agent run against its expected behaviour."""
    called = [c["tool"] for c in out["tool_calls"]]
    succeeded = [c["tool"] for c in out["tool_calls"] if not c["is_error"]]
    behaviour = case.get("expect_behaviour", "answer")
    checks = {"grounded": out["validation"]["ok"]}
    if behaviour == "answer":
        checks["right_tools"] = set(case["expect_tools"]) <= set(succeeded)
        checks["right_numbers"] = all(answer_contains(out["answer"], x) for x in case["expect_numbers"])
    elif behaviour == "ask":
        checks["no_tool_call"] = not called
        checks["asks_for_input"] = "?" in out["answer"]
    else:  # refuse
        checks["no_successful_call"] = not succeeded
    return {"id": case["id"], "passed": all(checks.values()), "checks": checks, "tools": called}


async def run_evals(cases=CASES, llm=None, audit_path=None):
    results = []
    for case in cases:
        try:
            out = await run_agent(case["question"], llm=llm, audit_path=audit_path)
            results.append(score_case(case, out))
        except Exception as exc:  # noqa: BLE001 - an eval must report failures, not crash
            results.append({"id": case["id"], "passed": False, "checks": {"error": str(exc)},
                            "tools": []})
    return results


def write_report(results, folder=Path("evals")):
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    passed = sum(r["passed"] for r in results)
    date = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    score = f"**Score: {passed}/{len(results)} passed ({100 * passed / len(results):.0f}%)**"
    lines = [
        "# Agent evaluation results",
        "",
        f"{score} | model `{MODEL}` | {date}",
        "",
        "| Case | Result | Tools called | Failed checks |",
        "|---|---|---|---|",
    ]
    for r in results:
        failed = [k for k, ok in r["checks"].items() if ok is not True] or ["-"]
        status = "PASS" if r["passed"] else "FAIL"
        tools = ", ".join(r["tools"]) or "-"
        lines.append(f"| {r['id']} | {status} | {tools} | {', '.join(failed)} |")
    (folder / "results.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (folder / "results.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    return passed


def main() -> None:
    results = asyncio.run(run_evals(audit_path=Path("logs/eval_audit.jsonl")))
    passed = write_report(results)
    print(f"{passed}/{len(results)} cases passed. Report: evals/results.md")