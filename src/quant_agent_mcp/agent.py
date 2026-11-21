"""LLM agent that answers trader requests by calling the MCP pricing tools."""
from __future__ import annotations

import asyncio
import json
import os
import sys

import anthropic
from mcp.client import Client

from quant_agent_mcp.server import mcp

MODEL = os.environ.get("QUANT_AGENT_MODEL", "claude-sonnet-5-5")
MAX_STEPS = 8
SYSTEM_PROMPT = """You are a quantitative analyst assistant for a trading desk.
Rules:
- Never compute or estimate a number yourself: every number in your answer must come from a tool.
- If an input is missing (for example volatility or maturity), ask for it instead of assuming.
- Rates and volatilities are decimals (5% = 0.05). Maturities are in years.
- Answer concisely and state the inputs you used."""


def _field(obj, *names, default=None):
    for name in names:
        if hasattr(obj, name):
            return getattr(obj, name)
    return default


async def list_tools_for_llm(client):
    listed = await client.list_tools()
    tools = _field(listed, "tools", default=listed)
    return [
        {
            "name": tool.name,
            "description": tool.description or "",
            "input_schema": _field(tool, "input_schema", "inputSchema"),
        }
        for tool in tools
    ]


def result_to_text(result):
    structured = _field(result, "structured_content", "structuredContent")
    if structured:
        return json.dumps(structured)
    parts = _field(result, "content", default=[]) or []
    return "\n".join(getattr(part, "text", str(part)) for part in parts)


async def run_agent(question, llm=None):
    llm = llm or anthropic.AsyncAnthropic()
    trace = []
    async with Client(mcp) as client:
        tools = await list_tools_for_llm(client)
        messages = [{"role": "user", "content": question}]
        for _ in range(MAX_STEPS):
            response = await llm.messages.create(
                model=MODEL, max_tokens=1024, system=SYSTEM_PROMPT, tools=tools, messages=messages
            )
            messages.append({"role": "assistant", "content": response.content})
            if response.stop_reason != "tool_use":
                answer = "".join(b.text for b in response.content if b.type == "text")
                return {"question": question, "answer": answer, "tool_calls": trace}
            results = []
            for block in response.content:
                if block.type != "tool_use":
                    continue
                result = await client.call_tool(block.name, block.input)
                is_error = bool(_field(result, "is_error", "isError", default=False))
                text = result_to_text(result)
                trace.append(
                    {"tool": block.name, "input": block.input, "output": text, "is_error": is_error}
                )
                results.append(
                    {"type": "tool_result", "tool_use_id": block.id, "content": text,
                     "is_error": is_error}
                )
            messages.append({"role": "user", "content": results})
        raise RuntimeError(f"Agent did not finish within {MAX_STEPS} steps.")


def main() -> None:
    question = " ".join(sys.argv[1:]) or input("Trader request: ")
    out = asyncio.run(run_agent(question))
    print(out["answer"])
    print(f"\n[{len(out['tool_calls'])} tool call(s)]")