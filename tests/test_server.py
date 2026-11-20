import asyncio
import inspect

import pytest

from quant_agent_mcp.server import (
    implied_volatility,
    mcp,
    option_greeks,
    price_option,
    yield_curve,
)


def test_price_option_returns_inputs_and_price():
    out = price_option(S=100, K=100, T=1, r=0.05, sigma=0.2)
    assert out["price"] == pytest.approx(10.4506, abs=1e-4)
    assert out["inputs"]["option"] == "call"


def test_implied_vol_tool_round_trip():
    price = price_option(S=100, K=100, T=1, r=0.05, sigma=0.3, option="put")["price"]
    out = implied_volatility(price=price, S=100, K=100, T=1, r=0.05, option="put")
    assert out["implied_vol"] == pytest.approx(0.3, abs=1e-8)


def test_greeks_tool_keys():
    out = option_greeks(S=100, K=100, T=1, r=0.05, sigma=0.2)
    assert set(out["greeks"]) == {"delta", "gamma", "vega", "theta", "rho"}


def test_yield_curve_tool():
    out = yield_curve([1, 2, 3], [0.03, 0.035, 0.04], [1, 2.5])
    assert len(out["points"]) == 2
    assert 0 < out["points"][1]["discount_factor"] < 1


def test_invalid_input_raises():
    with pytest.raises(ValueError):
        price_option(S=-1, K=100, T=1, r=0.05, sigma=0.2)



def test_tools_are_registered():
    tools = mcp.list_tools()
    if inspect.isawaitable(tools):
        tools = asyncio.run(tools)
    names = {tool.name for tool in tools}
    assert names == {"price_option", "option_greeks", "implied_volatility", "yield_curve"}