"""Evaluation harness: run representative trader requests through the agent and score them."""
from __future__ import annotations

import asyncio
import json
import os
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


CATEGORIES = {
    "atm_call_price": "Pricing",
    "atm_put_price": "Pricing",
    "otm_call_6m": "Pricing",
    "call_with_dividend": "Pricing",
    "call_delta_gamma": "Greeks",
    "put_price_and_delta": "Greeks",
    "implied_vol_call": "Implied volatility",
    "implied_vol_put": "Implied volatility",
    "curve_discount_factor": "Rates",
    "curve_zero_rate": "Rates",
    "missing_volatility": "Safety",
    "negative_spot": "Safety",
    "arbitrage_price": "Safety",
}


def closest_error(answer, expected):
    """Absolute error between `expected` and the closest number shown in the answer."""
    best = None
    for value, _, is_percent in extract_numbers(answer):
        for v in ([value, value / 100] if is_percent else [value]):
            err = abs(v - expected)
            best = err if best is None else min(best, err)
    return best

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
    max_error = None
    if behaviour == "answer":
        expected = case["expect_numbers"]
        checks["right_tools"] = set(case["expect_tools"]) <= set(succeeded)
        checks["right_numbers"] = all(answer_contains(out["answer"], x) for x in expected)
        errors = [closest_error(out["answer"], x) for x in expected]
        max_error = max((e for e in errors if e is not None), default=None)
    elif behaviour == "ask":
        checks["no_tool_call"] = not called
        checks["asks_for_input"] = "?" in out["answer"]
    else:  # refuse
        checks["no_successful_call"] = not succeeded
    return {
        "id": case["id"],
        "category": CATEGORIES.get(case["id"], "Other"),
        "passed": all(checks.values()),
        "checks": checks,
        "tools": called,
        "max_abs_error": max_error,
    }


async def run_evals(cases=CASES, llm=None, audit_path=None, runs=1):
    results = []
    for run in range(1, runs + 1):
        for case in cases:
            try:
                out = await run_agent(case["question"], llm=llm, audit_path=audit_path)
                result = score_case(case, out)
            except Exception as exc:  # noqa: BLE001 - an eval must report failures, not crash
                result = {
                    "id": case["id"],
                    "category": CATEGORIES.get(case["id"], "Other"),
                    "passed": False,
                    "checks": {"error": str(exc)},
                    "tools": [],
                    "max_abs_error": None,
                }
            result["run"] = run
            results.append(result)
    return results


def _rate(n, total):
    return f"{n}/{total} ({100 * n / total:.0f}%)" if total else "n/a"


def _max_error(rows):
    errors = [r["max_abs_error"] for r in rows if r["max_abs_error"] is not None]
    return f"{max(errors):.1e}" if errors else "-"


def write_report(results, folder=Path("evals")):
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    date = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    runs = max(r["run"] for r in results)
    by_case = {}
    for r in results:
        by_case.setdefault(r["id"], []).append(r)
    passed = sum(r["passed"] for r in results)
    consistent = sum(all(r["passed"] for r in rows) for rows in by_case.values())
    grounded = sum(r["checks"].get("grounded") is True for r in results)
    tool_rows = [r for r in results if "right_tools" in r["checks"]]
    right_tools = sum(r["checks"]["right_tools"] for r in tool_rows)
    safety = [r for r in results if r["category"] == "Safety"]
    safe = sum(r["passed"] for r in safety)
    header = f"Model `{MODEL}` | {date} | {len(by_case)} cases x {runs} run(s)"
    lines = [
        "# Agent evaluation report",
        "",
        header,
        "",
        "## Summary",
        "",
        "| Metric | Result |",
        "|---|---|",
        f"| Overall pass rate | {_rate(passed, len(results))} |",
        f"| Consistency (case passes in every run) | {_rate(consistent, len(by_case))} |",
        f"| Grounded answers (every number traced) | {_rate(grounded, len(results))} |",
        f"| Correct tool selection | {_rate(right_tools, len(tool_rows))} |",
        f"| Safe behaviour (asks or refuses when needed) | {_rate(safe, len(safety))} |",
        f"| Max abs. error vs reference (incl. display rounding) | {_max_error(results)} |",
        "",
        "## By category",
        "",
        "| Category | Runs | Pass rate | Max abs. error |",
        "|---|---|---|---|",
    ]
    for category in dict.fromkeys(r["category"] for r in results):
        rows = [r for r in results if r["category"] == category]
        rate = _rate(sum(r["passed"] for r in rows), len(rows))
        lines.append(f"| {category} | {len(rows)} | {rate} | {_max_error(rows)} |")
    lines += [
        "",
        "## Case details",
        "",
        "| Case | Category | Pass rate | Tools called | Failed checks |",
        "|---|---|---|---|---|",
    ]
    for case_id, rows in by_case.items():
        rate = _rate(sum(r["passed"] for r in rows), len(rows))
        tools = ", ".join(dict.fromkeys(t for r in rows for t in r["tools"])) or "-"
        failed = sorted({k for r in rows for k, ok in r["checks"].items() if ok is not True})
        category = rows[0]["category"]
        lines.append(f"| {case_id} | {category} | {rate} | {tools} | {', '.join(failed) or '-'} |")
    (folder / "results.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (folder / "results.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    return passed


def main() -> None:
    runs = int(os.environ.get("QUANT_AGENT_EVAL_RUNS", "3"))
    results = asyncio.run(run_evals(runs=runs, audit_path=Path("logs/eval_audit.jsonl")))
    passed = write_report(results)
    print(f"{passed}/{len(results)} agent runs passed. Report: evals/results.md")