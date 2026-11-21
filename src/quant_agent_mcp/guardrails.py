"""Output validation and audit logging for the quant agent."""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

NUMBER = re.compile(r"(?<![\w.])-?\d+(?:,\d{3})*(?:\.\d+)?%?")


def extract_numbers(text):
    """Numbers found in a text, as (value, number of decimals, is_percent)."""
    found = []
    for token in NUMBER.findall(text or ""):
        is_percent = token.endswith("%")
        raw = token.rstrip("%").replace(",", "")
        decimals = len(raw.split(".")[1]) if "." in raw else 0
        found.append((float(raw), decimals, is_percent))
    return found


def _collect(obj, out):
    """Collect every number inside tool inputs/outputs (dicts, lists, JSON strings)."""
    if isinstance(obj, bool):
        return
    if isinstance(obj, (int, float)):
        out.append(float(obj))
    elif isinstance(obj, dict):
        for value in obj.values():
            _collect(value, out)
    elif isinstance(obj, (list, tuple)):
        for value in obj:
            _collect(value, out)
    elif isinstance(obj, str):
        try:
            _collect(json.loads(obj), out)
        except ValueError:
            out.extend(value for value, _, _ in extract_numbers(obj))


def allowed_numbers(question, tool_calls):
    """Numbers the answer is allowed to contain: from the request or from tool calls."""
    allowed = []
    for value, _, is_percent in extract_numbers(question):
        allowed.append(value)
        if is_percent:
            allowed.append(value / 100)
    for call in tool_calls:
        _collect(call.get("input"), allowed)
        _collect(call.get("output"), allowed)
    return allowed


def _is_supported(value, decimals, allowed):
    tolerance = 0.5 * 10**-decimals + 1e-12  # accept normal rounding (10.4506 -> 10.45)
    return any(abs(value - a) <= tolerance for a in allowed)


def validate_answer(question, answer, tool_calls):
    """Flag every number in the answer that cannot be traced to the request or a tool."""
    allowed = allowed_numbers(question, tool_calls)
    unsupported = []
    for value, decimals, is_percent in extract_numbers(answer):
        candidates = [(value, decimals)]
        if is_percent:
            candidates.append((value / 100, decimals + 2))  # 63.68% -> 0.6368
        if not any(_is_supported(v, d, allowed) for v, d in candidates):
            unsupported.append(f"{value:g}{'%' if is_percent else ''}")
    return {"ok": not unsupported, "unsupported": unsupported}


def write_audit(record, path):
    """Append one JSON line per agent run to the audit log."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    entry = {"timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"), **record}
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False, default=str) + "\n")