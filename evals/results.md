# Agent evaluation results

**Score: 13/13 passed (100%)** | model `claude-sonnet-5-5` | 2026-11-22 02:13 UTC

| Case | Result | Tools called | Failed checks |
|---|---|---|---|
| atm_call_price | PASS | price_option | - |
| atm_put_price | PASS | price_option | - |
| otm_call_6m | PASS | price_option | - |
| call_with_dividend | PASS | price_option | - |
| call_delta_gamma | PASS | option_greeks | - |
| put_price_and_delta | PASS | price_option, option_greeks | - |
| implied_vol_call | PASS | implied_volatility | - |
| implied_vol_put | PASS | implied_volatility | - |
| curve_discount_factor | PASS | yield_curve | - |
| curve_zero_rate | PASS | yield_curve | - |
| missing_volatility | PASS | - | - |
| negative_spot | PASS | - | - |
| arbitrage_price | PASS | - | - |
