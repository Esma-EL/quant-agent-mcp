"""MCP server exposing deterministic pricing and rates tools."""
from __future__ import annotations

from typing import Literal

from mcp.server.mcpserver import MCPServer

from quant_agent_mcp.pricing import bs_price, greeks, implied_vol
from quant_agent_mcp.rates import YieldCurve

mcp = MCPServer("quant-agent-mcp")

Option = Literal["call", "put"]



def price_option(
    S: float, K: float, T: float, r: float, sigma: float, q: float = 0.0, option: Option = "call"
) -> dict:
    """Price a European option with Black-Scholes-Merton.

    S: spot price, K: strike, T: maturity in years, r: risk-free rate (0.05 = 5%),
    sigma: volatility (0.2 = 20%), q: dividend yield, option: "call" or "put".
    """
    inputs = {**locals()}
    return {"tool": "price_option", "inputs": inputs, "price": bs_price(**inputs)}



def option_greeks(
    S: float, K: float, T: float, r: float, sigma: float, q: float = 0.0, option: Option = "call"
) -> dict:
    """Greeks of a European option: delta, gamma, vega (per 1.00 vol), theta (per year), rho."""
    inputs = {**locals()}
    return {"tool": "option_greeks", "inputs": inputs, "greeks": greeks(**inputs)}



def implied_volatility(
    price: float, S: float, K: float, T: float, r: float, q: float = 0.0, option: Option = "call"
) -> dict:
    """Volatility implied by a market option price (raises if the price breaks no-arbitrage bounds)."""
    inputs = {**locals()}
    return {"tool": "implied_volatility", "inputs": inputs, "implied_vol": implied_vol(**inputs)}


def yield_curve(maturities: list[int], par_rates: list[float], times: list[float]) -> dict:
    """Bootstrap a discount curve from annual par swap rates and evaluate it.

    maturities: consecutive years 1..N, par_rates: one par rate per maturity (0.03 = 3%),
    times: maturities in years where to return discount factors and zero rates.
    """
    inputs = {**locals()}
    curve = YieldCurve(maturities, par_rates)
    points = [
        {"t": t, "discount_factor": curve.discount(t), "zero_rate": curve.zero_rate(t)}
        for t in times
    ]
    return {"tool": "yield_curve", "inputs": inputs, "points": points}


TOOLS = (price_option, option_greeks, implied_volatility, yield_curve)
for _tool in TOOLS:
    mcp.tool()(_tool)


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()