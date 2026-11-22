# Quant Agent MCP
![CI](https://github.com/Esma-EL/quant-agent-mcp/actions/workflows/ci.yml/badge.svg)

Agentic quant assistant: an MCP server exposes deterministic pricing tools
(Black-Scholes, Greeks, implied volatility, yield curve) and an agent answers
trader requests. Every number is computed by a tool, validated and logged.

## Architecture


```mermaid
flowchart LR
    A[Trader request] --> B[LLM agent<br/>Claude]
    B -->|1. calls a tool via MCP| C[Pricing tools<br/>tested code]
    C -->|2. returns exact numbers| B
    B -.->|repeats until it has<br/>all the numbers| B
    B -->|3. draft answer| D{Guardrail<br/>every number traced?}
    D -->|4. OK| E[Final answer<br/>to trader]
    D --> F[(Audit log)]
```

### Request flow

```mermaid
sequenceDiagram
    participant T as Trader
    participant A as Agent (Claude)
    participant S as MCP server
    participant G as Guardrail
    T->>A: Price a 1y ATM call and give me the delta
    A->>S: price_option(S=100, K=100, T=1, r=0.05, sigma=0.2)
    S-->>A: price = 10.4506
    A->>S: option_greeks(...)
    S-->>A: delta = 0.6368
    A->>G: draft answer + tool trace
    G->>G: append run to audit log
    G-->>T: answer + [OK] every number traced
```


## Quickstart


## Evaluation
