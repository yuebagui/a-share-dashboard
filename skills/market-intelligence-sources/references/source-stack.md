# Financial News And Market Intelligence Source Stack

## Professional Finance News

### Bloomberg

- Best use: real-time markets, cross-asset alerts, terminal functions, company/industry news, TOP/NI feeds, analyst context.
- Access model: Bloomberg Terminal, Bloomberg API/B-PIPE/Enterprise products, Bloomberg.com subscription, Bloomberg TV/live pages.
- Handling rule: do not claim full Bloomberg access unless the user provides it. If only public web access is available, treat Bloomberg headlines/articles as secondary media and verify with primary filings or official statements.
- Search patterns:
  - `site:bloomberg.com {company} {topic} latest`
  - `Bloomberg {ticker} {event} Reuters confirmation`
  - `{topic} Bloomberg Terminal headline timestamp` when the user provides terminal text.

### Reuters / LSEG

- Best use: fast global policy, geopolitics, company news, commodities, FX, rates, macro.
- Access model: Reuters.com public articles, Reuters/LSEG licensed feeds, Workspace/Eikon for professionals.
- Handling rule: use Reuters as high-reputation media, but verify filings, policy text, and official statements when available.
- Search patterns:
  - `site:reuters.com/markets {topic}`
  - `site:reuters.com/world {country} sanctions tariff export controls`

### Other Licensed Or High-Reputation Sources

- Dow Jones Newswires / WSJ: corporate, policy, markets.
- Financial Times: macro, policy, finance, global companies.
- AP: official/political facts and breaking-news confirmation.
- CNBC: markets, CEO interviews, live TV clips, earnings coverage.
- Nikkei Asia: Asia supply chain, Japan, China, semiconductors.
- Caixin, 第一财经, 财联社, 证券时报, 中国证券报: China markets and A-share catalysts.
- Wind / Choice: China professional market data, filings, consensus, sector data.

## Primary Official Sources

### US Policy And Regulators

- White House Briefings & Statements: `https://www.whitehouse.gov/briefings-statements/`
- White House Remarks: use the Remarks category under White House News.
- White House Presidential Actions: executive orders, proclamations, memoranda.
- Federal Reserve: FOMC statements, speeches, calendars, minutes.
- US Treasury: sanctions, OFAC, financing, FX reports.
- US Commerce/BIS: export controls, entity list, semiconductor restrictions.
- USTR: tariffs, Section 301, trade negotiations.
- SEC EDGAR APIs: `https://www.sec.gov/search-filings/edgar-application-programming-interfaces`
  - Company submissions: `https://data.sec.gov/submissions/CIK##########.json`
  - Company facts: `https://data.sec.gov/api/xbrl/companyfacts/CIK##########.json`

### China And A-Share

- 巨潮资讯: A-share reports, announcements, investor relations records.
- 上交所 / 深交所 / 北交所: inquiry letters, disciplinary actions, announcements.
- 证监会: regulation, penalties, IPO/refinancing rules.
- 央行 / 外汇局 / 国家统计局 / 发改委 / 商务部 / 工信部: macro, liquidity, industry policy.
- 财联社, 证券时报, 中国证券报, 上海证券报: A-share policy and intraday catalyst confirmation.

## Direct Personality Channels

### Donald Trump

- Truth Social: `https://truthsocial.com/@realDonaldTrump`
- White House official statements and remarks: use as policy-level confirmation.
- X account: verify current usage and timestamp before relying on it.
- Rule: classify as personal/social unless it appears in White House remarks, presidential actions, agency rules, or formal policy documents.

### Elon Musk

- X: `https://x.com/elonmusk`
- Company channels:
  - Tesla investor relations and SEC filings.
  - SpaceX official site/accounts when available.
  - xAI official site/accounts when available.
  - Neuralink and The Boring Company official channels.
- Rule: classify as personal/social unless confirmed by a company filing, press release, product page, regulator filing, or official livestream.

## Alert-To-Verification Flow

1. Alert source: Bloomberg headline, Reuters alert, X/Truth Social post, 财联社快讯, market move.
2. Primary check: official statement, filing, transcript, regulator page, company IR.
3. Timestamp check: source timezone, publish time, whether post was edited/reposted.
4. Market check: asset move after timestamp, sector breadth, volume confirmation.
5. Output label:
   - `一手官方`: filing, regulator, White House/Fed/Treasury, company IR.
   - `专业快讯`: Bloomberg/Reuters/Dow Jones/LSEG/Wind/Choice.
   - `高可信媒体`: FT/WSJ/AP/CNBC/Nikkei/Caixin.
   - `本人社媒`: direct Trump/Musk post, not policy by itself.
   - `待验证`: repost, screenshot, forum, anonymous account.

## Watchlist Ideas

- Trump: tariffs, China policy, chips/export controls, energy, crypto, Fed pressure, defense, immigration/labor costs.
- Musk: Tesla deliveries/pricing/FSD/robotaxi, SpaceX/Starlink launches and contracts, xAI model/product news, DOGE/policy comments, crypto-related posts.
- A-share channels: semiconductors, AI算力, 机器人, 低空经济, 卫星互联网, 军工, 有色/稀土, 汽车链, 储能, 创新药.

