---
name: finance-news-monitor
description: Use this skill for current financial news monitoring and synthesis across macro, rates, FX, commodities, equities, sectors, central banks, economic data, earnings, and market-moving headlines. Trigger when the user asks for 财经新闻, 最新市场消息, 宏观新闻, 盘前消息, 盘后复盘, market news, financial news, catalysts, or news that may affect stocks, sectors, indices, bonds, currencies, commodities, or crypto.
---

# Finance News Monitor

## Core Rule

For any current or recent news, browse or otherwise verify with current sources before answering. State the date and timezone of the news window. Separate:

- Confirmed facts: dated source, event, numbers, official statement.
- Market reaction: price moves, sector moves, rates, FX, commodity changes.
- Interpretation: plausible impact and uncertainty.
- Watch items: next data release, decision date, guidance, earnings call, regulator notice.

Do not treat a headline aggregator, forum post, screenshot, or unsourced social post as a verified fact.

## Source Priority

For a fuller source stack, including Bloomberg, Reuters, SEC EDGAR, White House, Truth Social, X, Trump, and Musk monitoring, use `../market-intelligence-sources/references/source-stack.md` when available.

Use primary and high-reputation sources first:

1. Official releases: central banks, finance ministries, statistics agencies, exchanges, regulators, company IR.
2. Company disclosures: earnings releases, 8-K/6-K/10-Q/10-K/20-F, exchange announcements, 巨潮资讯, HKEXnews.
3. Reputable news: Reuters, Bloomberg, Financial Times, Wall Street Journal, CNBC, Associated Press, Nikkei Asia, Caixin, 第一财经, 财联社, 证券时报.
4. Market data: exchange pages, official index pages, Yahoo Finance, Nasdaq, CME, ICE, Eastmoney, Sina, TradingView.

When sources conflict, prefer primary sources and explain the discrepancy.

## Workflow

1. Define the requested market, asset, sector, company, and time window.
2. Gather at least two independent sources for major claims unless the source is an official disclosure.
3. Verify numbers: release date, period, consensus if available, actual value, prior value, revision.
4. Link the event to market channels: earnings, rates, liquidity, risk appetite, regulation, supply chain, demand, margin, valuation.
5. Identify what has already been priced in versus what remains unresolved.

## Output

Use this structure for news briefs:

- Headline: one sentence with the main event and timestamp.
- What happened: verified facts with sources.
- Market reaction: relevant asset moves if available.
- Why it matters: direct and second-order impact.
- Watch next: dates, filings, calls, policy events, data releases.
- Confidence: high, medium, or low, with the reason.

For A-share mapping, add:

- A股映射: direct beneficiaries, indirect beneficiaries, sentiment-only names.
- 验证要求: whether listed companies have disclosed orders, customers, capacity, revenue contribution, or risk exposure.
