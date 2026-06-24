---
name: a-share-daily-review
description: Use this skill for A-share daily market review, pre-market brief, post-market recap, index context, sector rotation, market breadth, limit-up/down analysis, northbound/southbound funds, capital flow, sentiment cycle, and next-day watchlist. Trigger when the user asks for A股复盘, 盘前, 盘后, 今日行情, 明日策略, 市场情绪, 涨停板, 跌停板, 主线, 轮动, or 指数分析.
---

# A-Share Daily Review

## Core Rule

For daily A-share market work, use current sources or local market-data scripts before concluding. Always include the trade date and data source. If data is unavailable, say so and avoid pretending that old or sample data is current.

Separate:

- Market facts: index moves, turnover, breadth, limit-up/down count, sector performance.
- Drivers: policy, macro, liquidity, earnings, industry news, overseas catalysts.
- Interpretation: risk appetite, rotation strength, crowded trades, divergence.
- Plan: scenarios and invalidation, not return promises.

## Workflow

1. Check market calendar and trade date.
2. Gather index context: 上证指数, 深证成指, 创业板指, 科创50, 北证50.
3. Gather breadth and liquidity: total turnover, up/down ratio, limit-up/down count, consecutive-board stocks if available.
4. Identify sector/theme leaders and laggards.
5. Separate true main line from one-day rebounds:
   - Main line: repeated strength, leader confirmation, volume support, news continuity.
   - Rebound: oversold bounce, weak follow-through, no fresh catalyst.
6. Find tomorrow's watch items: policy events, earnings, overseas data, sector catalysts, risk points.

## Output

Use this structure:

- Market snapshot: trade date, index moves, turnover, breadth.
- Main lines: 2-4 strongest themes and evidence.
- Weak spots: sectors or risk signals.
- Key catalysts: verified news and upcoming events.
- Tomorrow plan: bullish, neutral, bearish scenarios.
- Watchlist: names or sectors, with reason and invalidation.

