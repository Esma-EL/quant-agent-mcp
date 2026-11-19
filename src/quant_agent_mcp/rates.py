"""Yield curve bootstrapping from annual par swap rates."""
from __future__ import annotations

import math

import numpy as np


class YieldCurve:
    """Discount curve bootstrapped from par rates with annual coupons.

    Interpolation is log-linear on discount factors (piecewise-constant forwards).
    """

    def __init__(self, maturities, par_rates):
        mats = [int(m) for m in maturities]
        if not mats or len(mats) != len(par_rates):
            raise ValueError("maturities and par_rates must be non-empty and the same length.")
        if mats != list(range(1, len(mats) + 1)):
            raise ValueError("maturities must be consecutive years: 1, 2, ..., N.")
        dfs = []
        for c in par_rates:
            df = (1.0 - c * sum(dfs)) / (1.0 + c)
            if df <= 0:
                raise ValueError("Bootstrapping produced a non-positive discount factor.")
            dfs.append(df)
        self.times = np.array([0.0, *map(float, mats)])
        self.dfs = np.array([1.0, *dfs])

    def discount(self, t):
        """Value today of 1 paid at time t (years)."""
        if not 0 <= t <= self.times[-1]:
            raise ValueError(f"t must be in [0, {self.times[-1]:g}] years.")
        return float(np.exp(np.interp(t, self.times, np.log(self.dfs))))

    def zero_rate(self, t):
        """Continuously compounded zero rate."""
        if t <= 0:
            raise ValueError("t must be positive.")
        return -math.log(self.discount(t)) / t

    def forward_rate(self, t1, t2):
        """Continuously compounded forward rate between t1 and t2."""
        if not t2 > t1:
            raise ValueError("t2 must be greater than t1.")
        return math.log(self.discount(t1) / self.discount(t2)) / (t2 - t1)