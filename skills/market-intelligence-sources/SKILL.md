---
name: market-intelligence-sources
description: Use this skill to build or use a financial news and market-intelligence source stack, including Bloomberg, Reuters, Dow Jones, CNBC, Financial Times, SEC EDGAR, White House, Federal Reserve, Treasury, Truth Social, X/Twitter, Elon Musk, Donald Trump, company IR, exchange filings, sanctions/export-control notices, and real-time market-moving public statements. Trigger when the user asks for 财经新闻源, 信息源, 数据源, 彭博, 路透, 实时发言, 特朗普发言, 马斯克发言, Twitter/X, Truth Social, 舆情监控, news monitoring, or market intelligence.
---

# Market Intelligence Sources

## Core Rule

Treat market-moving information as a source-quality problem before it is an analysis problem. For current information, verify the timestamp, original publisher, and whether the item is primary, licensed professional news, reputable media, or social repost.

Never present paywalled Bloomberg/Reuters/Dow Jones content as directly available unless the user has subscription, terminal, API, or licensed access. Use public summaries only as secondary context.

## Source Tiers

Use `references/source-stack.md` for source lists and access notes.

1. Primary official: regulators, exchanges, central banks, White House, Treasury, SEC, company IR, exchange filings.
2. Licensed professional: Bloomberg Terminal/API, Bloomberg News, Reuters/LSEG, Dow Jones Newswires, FactSet, Wind, Choice.
3. Reputable public media: CNBC, FT, WSJ, AP, Nikkei, Caixin, 第一财经, 财联社, 证券时报.
4. Direct personality channels: Truth Social, X, official livestreams, official transcripts.
5. Aggregators and social: useful for alerts, not verification.

## Workflow

1. Define watch target:
   - Person: Trump, Musk, Powell, Treasury Secretary, company CEO.
   - Institution: White House, Fed, SEC, Treasury, Commerce, exchange, company.
   - Asset: A-share sector, US stock, FX, rates, oil, gold, crypto.
2. Choose source tier:
   - Use primary official sources for statements and policy.
   - Use professional news if the user has access or asks for provider coverage.
   - Use social channels only for direct posts or early alerts.
3. Capture metadata:
   - Source URL or provider
   - Published time and timezone
   - Author/account
   - Original quote or paraphrase
   - Asset/channel likely affected
4. Cross-check before analysis:
   - Is this a new statement or repost of old content?
   - Is it official policy or personal commentary?
   - Is there a transcript, filing, order, or company release?
   - Did markets move after the timestamp?
5. Output facts, then impact. Do not jump from a social post to a trade call without confirming liquidity, sector context, and price reaction.

## Output

Use this structure:

- Source status: primary/licensed/media/social, with timestamp.
- What was said/reported: concise, attributed summary.
- Verification: confirming or conflicting sources.
- Market channel: policy, rates, tariffs, supply chain, Tesla/SpaceX/xAI, AI, crypto, defense, energy, China/A股.
- Affected assets: direct, indirect, sentiment-only.
- Watch next: follow-up source, filing, transcript, press conference, market open.

