import math
from itertools import pairwise

import pytest

from quant_agent_mcp.rates import YieldCurve

MATS = [1, 2, 3, 4, 5]
PARS = [0.030, 0.034, 0.037, 0.039, 0.040]


def test_flat_par_curve_gives_flat_annual_discounting():
    curve = YieldCurve(MATS, [0.05] * 5)
    for n in MATS:
        assert curve.discount(n) == pytest.approx(1.05**-n, rel=1e-12)


def test_bootstrapped_curve_reprices_par_swaps():
    curve = YieldCurve(MATS, PARS)
    for n, c in zip(MATS, PARS, strict=True):
        annuity = sum(curve.discount(i) for i in range(1, n + 1))
        assert c * annuity + curve.discount(n) == pytest.approx(1.0, abs=1e-12)


def test_discount_is_one_today_and_decreasing():
    curve = YieldCurve(MATS, PARS)
    assert curve.discount(0) == 1.0
    dfs = [curve.discount(0.5 * i) for i in range(11)]
    assert all(a > b for a, b in pairwise(dfs))


def test_forward_rate_consistency():
    curve = YieldCurve(MATS, PARS)
    f = curve.forward_rate(2, 3)
    assert curve.discount(3) == pytest.approx(curve.discount(2) * math.exp(-f), rel=1e-12)


@pytest.mark.parametrize("mats, pars", [([1, 3], [0.03, 0.04]), ([1, 2], [0.03]), ([], [])])
def test_invalid_inputs_raise(mats, pars):
    with pytest.raises(ValueError):
        YieldCurve(mats, pars)


def test_out_of_range_maturity_raises():
    with pytest.raises(ValueError):
        YieldCurve(MATS, PARS).discount(6)