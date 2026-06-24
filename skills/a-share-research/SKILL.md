---
name: a-share-research
description: Use this skill for A-share investing research, including daily A-share prices, company announcements, financial reports, sector themes, frontier finance/technology news, and short-term or swing-trading decision support. Trigger when the user asks about A股, 个股, 板块, 持仓诊断, 财报, 公告, 题材, 热点, 盘前策略, 盘后复盘, or market-moving technology/news catalysts.
---

# A-Share Research

## Core Rule

Always separate facts, inference, and trading plan.

- Facts: verified prices, announcements, financial metrics, dates, and news sources.
- Inference: what the facts may mean for sentiment, valuation, business quality, or catalysts.
- Trading plan: position sizing, entry/exit conditions, stop loss, take profit, and invalidation.

For current market data, prices, announcements, news, regulations, financial reports, or anything that could have changed recently, browse or otherwise verify with current sources before giving a conclusion.

If a local dashboard/data script exists, run it with the workspace virtual environment first and inspect `meta.tradeDate`, `meta.source`, and `meta.errors`. Never treat sample data as market data.

## Source Priority

Use the source map in `references/source-map.md` when source choice matters.

Priority order:

1. Official disclosures: 巨潮资讯, 上交所, 深交所, 北交所, HKEX if relevant.
2. Company investor relations and official announcements.
3. Exchange or regulator data: CSRC, SAFE, PBOC, NBS, exchange bulletins.
4. Market data portals: 东方财富, 同花顺, 新浪财经, Wind/Choice if available through user-provided access.
5. Reputable financial and technology news: 证券时报, 上海证券报, 中国证券报, 财联社, 36氪, 晚点, The Information, Bloomberg, Reuters, CNBC, TechCrunch, Axios.

Do not treat forum posts, stock bar comments, reposted screenshots, or unsourced social media as reliable facts. They can be used only as sentiment clues.

## Daily A-Share Workflow

For a daily market or stock request, gather:

1. Index context: 上证指数, 深证成指, 创业板指, 科创50, 北证50 if relevant.
2. Target price action: latest price, percent change, volume/turnover, recent high/low, key moving averages if available.
3. Sector context: concept boards, industry boards, leading/lagging peers.
4. News/catalysts: official announcements first, then market-moving news.
5. Risk events: earnings dates, lock-up expiry, regulatory action, pledge/reduction plans, litigation, customer concentration, valuation stretch.

For short-term trading, make the conclusion conditional:

- Bullish continuation requires: volume confirmation, sector strength, and price holding above the chosen invalidation level.
- Rebound trade requires: shrinking downside volume, stabilization near support, or clear catalyst timing.
- Exit/reduce requires: broken support, failed breakout, sector leader weakness, or catalyst exhaustion.

## Financial Report Workflow

When analyzing financial reports:

1. Verify report period and release date.
2. Extract revenue, net profit,扣非净利润, gross margin, net margin, operating cash flow, inventory, receivables, capex, R&D expense, debt, and guidance if disclosed.
3. Compare year-over-year and quarter-over-quarter.
4. Check whether profit growth is supported by cash flow and core operations.
5. Identify one bullish point, one bearish point, and one data point that needs follow-up.

For A-share companies, avoid relying only on summary articles. Use official reports when possible.

## Frontier Finance And Technology News

For themes like SpaceX, Starlink, AI, semiconductors, robotics, low-altitude economy, solid-state batteries, humanoid robots, satellite internet, or biotech:

1. Verify the global catalyst from primary or reputable sources.
2. Map it to the A-share value chain.
3. Distinguish direct exposure, indirect exposure, and pure sentiment exposure.
4. Check whether the listed company has disclosed the relevant customer/product/order.
5. Warn when market logic is only thematic and not yet backed by revenue or orders.

## Output Templates

### Stock Diagnosis

Use this structure:

- Verdict: one sentence, with confidence level.
- Current facts: price, change, volume, latest announcement/news.
- Core logic: why the stock may rise or fall.
- Key levels: support, resistance, invalidation, event window.
- Position plan: hold/reduce/add/watch, with position percentage.
- Biggest risk: the one thing that would make the thesis wrong.

### Portfolio Risk

Use this structure:

- Account status: capital, current loss, max acceptable loss, remaining risk budget.
- Concentration risk: single-name and sector exposure.
- Action plan: immediate position control, stop-loss rule, rebound rule, cash reserve.
- Review date: when to re-evaluate.

## Guardrails

Do not promise returns. Do not present rumors as verified facts. Do not encourage full-position speculation unless the user explicitly accepts extreme risk and the plan includes a hard stop. When the user is already emotionally or financially stressed, prioritize risk budget and decision clarity.
