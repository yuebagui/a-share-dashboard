---
name: a-share-portfolio-risk
description: Use this skill for A-share portfolio diagnosis and risk control, including position sizing, concentration risk, drawdown control, stop-loss plans, take-profit rules, sector exposure, capital allocation, rebound rules, and emotional trading guardrails. Trigger when the user asks about 持仓诊断, 仓位, 亏损, 回撤, 止损, 止盈, 补仓, 减仓, 满仓, 风控, or portfolio risk.
---

# A-Share Portfolio Risk

## Core Rule

Prioritize survival, liquidity, and decision clarity. Do not promise recovery or returns. When the user is under stress, reduce the decision to risk budget, invalidation level, and next action.

Separate:

- Account facts: capital, position sizes, cost basis, current price, unrealized gain/loss.
- Market facts: trend, sector strength, liquidity, catalyst.
- Risk decision: hold, reduce, exit, add only under conditions.

## Workflow

1. Gather:
   - Total capital and cash
   - Each position: ticker, name, cost, shares/weight, current price
   - Maximum acceptable loss and time horizon
2. Calculate:
   - Single-name concentration
   - Sector/theme concentration
   - Current drawdown and remaining risk budget
   - Required rebound to breakeven if useful
3. Classify holdings:
   - Core with verified fundamentals
   - Event/catalyst trade
   - Theme/sentiment trade
   - Broken thesis or liquidity trap
4. Set rules:
   - Stop-loss or reduce level
   - Rebound selling level
   - Add condition only if thesis, trend, and risk budget align
   - Cash reserve floor

## Output

Use this structure:

- Portfolio status: capital, cash, drawdown, concentration.
- Biggest risk: one sentence.
- Position actions: hold/reduce/exit/watch/add-conditionally.
- Risk budget: max loss and stop levels.
- Rebound plan: what to do if the market gives a bounce.
- Review date: when to reassess.

