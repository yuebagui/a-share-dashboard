---
name: a-share-realtime-quote
description: Fetch current A-share realtime quotes with an Eastmoney-first, Tencent-second, Sina-third fallback chain. Use when Codex needs the latest stock price, intraday change, open/high/low/previous close, volume, amount, or a quick live quote check for A-share codes such as 300136, sz300136, sh600519, or 600519.
---

# A-Share Realtime Quote

## Quick Start

Run the bundled script from the workspace root:

```bash
.venv/bin/python skills/a-share-realtime-quote/scripts/realtime_quote.py 300136
```

Use `--json` when another script or analysis needs machine-readable output:

```bash
.venv/bin/python skills/a-share-realtime-quote/scripts/realtime_quote.py sz300136 --json
```

## Workflow

1. Normalize the user-provided code.
   - `300136` becomes `sz300136`.
   - `600519` becomes `sh600519`.
   - Existing prefixes like `sz300136` or `sh600519` are preserved.
2. Fetch realtime quote data through the fallback chain:
   - Eastmoney `push2` single-stock quote API.
   - Tencent `qt.gtimg.cn`.
   - Sina `hq.sinajs.cn`.
3. Report the first successful quote and include failed source errors when all sources fail or when `--verbose` is passed.
4. If live quote fetching is blocked by sandbox/network policy, rerun the same command with escalated network permission.

## Output Rules

- Treat `price`, `open`, `high`, `low`, and `prev_close` as yuan-denominated prices.
- Treat `change_pct` as percent, not decimal.
- Treat `volume` as shares when the source provides enough information to normalize it.
- Do not invent a quote when all three sources fail; return the error list.

## Notes

- Eastmoney is preferred because it aligns with the project dashboard data source.
- Tencent and Sina are included because Eastmoney occasionally closes proxy connections or rate-limits public quote endpoints.
- For trading decisions, combine this live quote with K-line/ATR/MA20 analysis from `stock-timing-analysis`; a realtime price alone is not a buy/sell signal.
