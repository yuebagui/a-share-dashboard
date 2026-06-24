---
name: short-term-stock-calculator
description: Calculate a personalized short-term A-share trading score for a single stock code using realtime quote, daily K-line, MA20, ATR, MACD, volume-price behavior, 20cm/leader/trend mode fit, stop-loss risk, and the user's system for 龙头容量趋势、20cm、连板、分歧低吸、突破. Use when the user gives an A-share code and asks whether it is worth buying, holding, selling, scoring, or short-term analysis.
---

# Short-Term Stock Calculator

## Quick Start

From the workspace root, run:

```bash
.venv/bin/python skills/short-term-stock-calculator/scripts/calculator.py 300750
```

Machine-readable output:

```bash
.venv/bin/python skills/short-term-stock-calculator/scripts/calculator.py 300750 --json
```

Optional mode hints:

```bash
.venv/bin/python skills/short-term-stock-calculator/scripts/calculator.py 300750 --mode 20cm
.venv/bin/python skills/short-term-stock-calculator/scripts/calculator.py 600519 --mode trend
.venv/bin/python skills/short-term-stock-calculator/scripts/calculator.py 000001 --mode leader
```

If quote or K-line fetching is blocked by sandbox/network policy, rerun the same command with escalated network permission.

## Workflow

When the user provides a stock code:

1. Normalize the code:
   - `300xxx`, `000xxx`, `002xxx`, `003xxx` -> `sz`.
   - `600xxx`, `601xxx`, `603xxx`, `605xxx`, `688xxx`, `689xxx` -> `sh`.
2. Run the calculator script.
3. If the user also provided market context, theme, 龙头地位, or current holding cost, incorporate it in the final interpretation.
4. If the script lacks current data, state the failure and do not invent a score.

## Scoring Meaning

The script outputs a 100-point score:

- `90+`: strong candidate, only if market情绪 and main-line status also confirm.
- `80-89`: standard candidate, normal position if the planned buy point triggers.
- `70-79`: trial candidate, small position only.
- `<70`: avoid or wait.

Hard vetoes override score:

- Top-divergence or obvious high-volume stalling.
- Trend breakdown below MA20 with weak rebound.
- Unclear stop-loss, or expected loss exceeds 5%.
- Market退潮 / high-position亏钱效应扩散.

## Output Rules

Answer in Chinese using this structure:

1. **结论**: score, action, confidence, data time.
2. **分项评分**: theme/core caveat if not provided, trend, volume-price, position, volatility, buy-point fit, risk.
3. **模式匹配**: 龙头分歧低吸 / 容量趋势突破 / 20cm反包低吸, and which one fits best.
4. **关键价位**: support, resistance, MA20, ATR stop reference.
5. **操作计划**:
   - 买入条件.
   - 止损条件.
   - 仓位 suggestion based on score and market state.
6. **风险提示**: short, practical, no return promises.

Do not say "可以买" solely because the score is high. Require a valid buy-point trigger and stop-loss.

## User-Specific Rules

The user's profile:

- Trades 20cm, 连板, low吸反包, and breakthrough.
- Prefers 龙头容量趋势结合.
- Common problems: buys too early, slow stop-loss, weak leader selection, emotional overtrading.
- Risk limits: 5% max loss per trade, 20% max account drawdown.
- Account size: 10-50万; default to 2-4 positions.
- Can only watch market intermittently.

Therefore:

- If score is under 80, default to "观察或小仓试错", not aggressive.
- If stop distance is above 5%, reduce position or wait for a better entry.
- If the best plan requires constant intraday watching, say it is not ideal for the user's schedule.
- Favor pre-planned entries: 分歧低吸 at support, breakthrough confirmation, or shrink-volume pullback.

