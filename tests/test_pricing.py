import math

import pytest

from quant_agent_mcp.pricing import bs_price, greeks, implied_vol

BASE = {"S": 100.0, "K": 100.0, "T": 1.0, "r": 0.05, "sigma": 0.2}


def test_reference_values():
    assert bs_price(**BASE, option="call") == pytest.approx(10.4506, abs=1e-4)
    assert bs_price(**BASE, option="put") == pytest.approx(5.5735, abs=1e-4)


@pytest.mark.parametrize("q", [0.0, 0.03])
def test_put_call_parity(q):
    c = bs_price(**BASE, q=q, option="call")
    p = bs_price(**BASE, q=q, option="put")
    S, K, T, r = BASE["S"], BASE["K"], BASE["T"], BASE["r"]
    assert c - p == pytest.approx(S * math.exp(-q * T) - K * math.exp(-r * T), abs=1e-10)


@pytest.mark.parametrize("option", ["call", "put"])
def test_greeks_match_finite_differences(option):
    g = greeks(**BASE, q=0.02, option=option)
    h = 1e-4

    def price(**kw):
        return bs_price(**{**BASE, "q": 0.02, "option": option, **kw})

    S, sig, r, T = BASE["S"], BASE["sigma"], BASE["r"], BASE["T"]
    assert g["delta"] == pytest.approx((price(S=S + h) - price(S=S - h)) / (2 * h), rel=1e-5)
    assert g["gamma"] == pytest.approx((price(S=S + h) - 2 * price() + price(S=S - h)) / h**2, rel=1e-3)
    assert g["vega"] == pytest.approx((price(sigma=sig + h) - price(sigma=sig - h)) / (2 * h), rel=1e-5)
    assert g["rho"] == pytest.approx((price(r=r + h) - price(r=r - h)) / (2 * h), rel=1e-5)
    assert g["theta"] == pytest.approx(-(price(T=T + h) - price(T=T - h)) / (2 * h), rel=1e-4)


@pytest.mark.parametrize(
    "bad", [{"S": -1}, {"K": 0}, {"T": 0}, {"sigma": 0}, {"option": "swap"}]
)
def test_invalid_inputs_raise(bad):
    with pytest.raises(ValueError):
        bs_price(**{**BASE, **bad})

@pytest.mark.parametrize("option", ["call", "put"])
@pytest.mark.parametrize("sigma", [0.05, 0.2, 0.6, 1.5])
def test_implied_vol_round_trip(option, sigma):
    price = bs_price(**{**BASE, "sigma": sigma}, option=option)
    args = {k: v for k, v in BASE.items() if k != "sigma"}
    assert implied_vol(price, **args, option=option) == pytest.approx(sigma, abs=1e-8)


def test_implied_vol_reference():
    args = {k: v for k, v in BASE.items() if k != "sigma"}
    assert implied_vol(10.4506, **args, option="call") == pytest.approx(0.2, abs=1e-4)


@pytest.mark.parametrize("price", [0.0, 150.0])
def test_implied_vol_rejects_arbitrage_prices(price):
    args = {k: v for k, v in BASE.items() if k != "sigma"}
    with pytest.raises(ValueError):
        implied_vol(price, **args, option="call")