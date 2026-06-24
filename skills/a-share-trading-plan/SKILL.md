---
name: a-share-trading-plan
description: Use this skill for A-share short-term and swing trading plans, including entries, exits, stop loss, take profit, invalidation, event windows, sector confirmation, volume-price analysis, breakout/rebound setups, and watchlist construction. Trigger when the user asks whether to buy, sell, hold, add, reduce, chase, wait, trade tomorrow, or make a 短线, 波段, 买卖计划, or 交易计划.
---

# A-Share Trading Plan

## Core Rule

Every trading answer must be conditional. A useful plan includes entry, invalidation, position size, catalyst window, and exit logic. Do not give full-position speculative calls.

For current price, volume, sector strength, or news, verify with current sources or local scripts before giving levels.

## Setup Types

- Breakout continuation: price breaks resistance with volume, sector leader confirms.
- Pullback buy: price holds support after prior trend, volume shrinks on decline.
- Oversold rebound: downside momentum slows, catalyst or index stabilization appears.
- Event trade: clear announcement/earnings/policy window, predefined exit after event.
- Avoid: weak sector, no volume, broken support, unclear catalyst, already crowded narrative.

## Workflow

1. Define timeframe: intraday, 1-3 days, 1-2 weeks, or medium-term.
2. Verify:
   - Latest price and volume
   - Support/resistance
   - Sector/theme strength
   - Catalyst and risk events
3. Choose setup type.
4. Define plan:
   - Entry zone
   - Initial position size
   - Add condition
   - Stop/invalidation
   - Take-profit/reduce rules
   - Time stop if catalyst fails
5. State what would change the plan.

## Output

Use this structure:

- Verdict: trade/watch/avoid, with confidence.
- Setup: breakout, pullback, rebound, event, or avoid.
- Entry: price/condition, not just a direction.
- Stop: invalidation level or condition.
- Take profit: staged reduce rules.
- Position: conservative percentage.
- Review trigger: when to update the plan.

