"""Black-Scholes-Merton pricing and Greeks for European options."""
from __future__ import annotations

import math

from scipy.optimize import brentq
from scipy.stats import norm

OPTION_TYPES = ("call", "put")


def _validate(S, K, T, sigma, option):
    if S <= 0 or K <= 0:
        raise ValueError("Spot S and strike K must be positive.")
    if T <= 0:
        raise ValueError("Maturity T must be positive (in years).")
    if sigma <= 0:
        raise ValueError("Volatility sigma must be positive.")
    if option not in OPTION_TYPES:
        raise ValueError(f"option must be one of {OPTION_TYPES}.")


def d1_d2(S, K, T, r, sigma, q=0.0):
    d1 = (math.log(S / K) + (r - q + 0.5 * sigma**2) * T) / (sigma * math.sqrt(T))
    return d1, d1 - sigma * math.sqrt(T)


def bs_price(S, K, T, r, sigma, q=0.0, option="call"):
    """Price of a European option."""
    _validate(S, K, T, sigma, option)
    d1, d2 = d1_d2(S, K, T, r, sigma, q)
    df_r, df_q = math.exp(-r * T), math.exp(-q * T)
    if option == "call":
        return S * df_q * norm.cdf(d1) - K * df_r * norm.cdf(d2)
    return K * df_r * norm.cdf(-d2) - S * df_q * norm.cdf(-d1)


def greeks(S, K, T, r, sigma, q=0.0, option="call"):
    """Analytical Greeks. Vega and rho per 1.00 change, theta per year."""
    _validate(S, K, T, sigma, option)
    d1, d2 = d1_d2(S, K, T, r, sigma, q)
    df_r, df_q = math.exp(-r * T), math.exp(-q * T)
    pdf_d1, sqrt_t = norm.pdf(d1), math.sqrt(T)

    gamma = df_q * pdf_d1 / (S * sigma * sqrt_t)
    vega = S * df_q * pdf_d1 * sqrt_t
    if option == "call":
        delta = df_q * norm.cdf(d1)
        theta = (-S * df_q * pdf_d1 * sigma / (2 * sqrt_t)
                 - r * K * df_r * norm.cdf(d2) + q * S * df_q * norm.cdf(d1))
        rho = K * T * df_r * norm.cdf(d2)
    else:
        delta = -df_q * norm.cdf(-d1)
        theta = (-S * df_q * pdf_d1 * sigma / (2 * sqrt_t)
                 + r * K * df_r * norm.cdf(-d2) - q * S * df_q * norm.cdf(-d1))
        rho = -K * T * df_r * norm.cdf(-d2)
    return {"delta": delta, "gamma": gamma, "vega": vega, "theta": theta, "rho": rho}


def implied_vol(price, S, K, T, r, q=0.0, option="call", lo=1e-6, hi=5.0):
    """Volatility that reproduces a given option price (Brent's root-finding method)."""
    _validate(S, K, T, 0.2, option)
    fwd_s, fwd_k = S * math.exp(-q * T), K * math.exp(-r * T)
    if option == "call":
        lower, upper = max(fwd_s - fwd_k, 0.0), fwd_s
    else:
        lower, upper = max(fwd_k - fwd_s, 0.0), fwd_k
    if not lower < price < upper:
        raise ValueError(f"Price {price} outside no-arbitrage bounds ({lower:.4f}, {upper:.4f}).")
    return brentq(lambda sig: bs_price(S, K, T, r, sig, q, option) - price, lo, hi, xtol=1e-10)