import asyncio
from types import SimpleNamespace as NS

from quant_agent_mcp.agent import run_agent


class FakeMessages:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        return self.responses.pop(0)


class FakeLLM:
    def __init__(self, responses):
        self.messages = FakeMessages(responses)


ATM_CALL = {"S": 100, "K": 100, "T": 1, "r": 0.05, "sigma": 0.2}


def test_agent_calls_mcp_tool_and_returns_answer():
    tool_use = NS(type="tool_use", id="t1", name="price_option", input=ATM_CALL)
    llm = FakeLLM([
        NS(stop_reason="tool_use", content=[tool_use]),
        NS(stop_reason="end_turn", content=[NS(type="text", text="The call is worth 10.45.")]),
    ])
    out = asyncio.run(run_agent("Price a 1y ATM call", llm=llm))
    call = out["tool_calls"][0]
    assert out["answer"] == "The call is worth 10.45."
    assert call["tool"] == "price_option"
    assert "10.45" in call["output"]
    assert not call["is_error"]
    assert "price_option" in {t["name"] for t in llm.messages.calls[0]["tools"]}


def test_agent_reports_tool_errors_to_the_model():
    bad = NS(type="tool_use", id="t1", name="price_option", input={**ATM_CALL, "S": -1})
    llm = FakeLLM([
        NS(stop_reason="tool_use", content=[bad]),
        NS(stop_reason="end_turn", content=[NS(type="text", text="Invalid spot price.")]),
    ])
    out = asyncio.run(run_agent("Price with S=-1", llm=llm))
    assert out["tool_calls"][0]["is_error"]
    