# A-Share Source Map

## Official Disclosure

- 巨潮资讯: annual reports, interim reports, quarterly reports, announcements, investor relations activity records.
- 上交所, 深交所, 北交所: listing rules, inquiry letters, disciplinary actions, company announcements.
- 证监会: regulatory policy, penalties, IPO/refinancing rules.

## Market Data

- AkShare: preferred local wrapper for Eastmoney, THS, Sina, CNInfo, and other public A-share data sources when installed in the workspace. Use it for repeatable dashboard/data generation.
- 东方财富: price, volume, capital flow pages, concept boards, financial summaries.
- 同花顺: concept classification, market heat, stock pages.
- 新浪财经: quick stock quotes and historical quote pages.
- TradingView or exchange quote pages can be used for chart context when accessible.

## News

- 财联社: A-share intraday catalysts and sector news.
- 证券时报, 上海证券报, 中国证券报: official/semi-official market coverage.
- 每日经济新闻, 21财经, 第一财经: company and industry reporting.
- 36氪, 晚点, 钛媒体: China technology and startup news.
- Reuters, Bloomberg, CNBC, TechCrunch, Axios, The Information: global technology and finance catalysts.

## Search Patterns

Use these query patterns:

- `{股票名} {股票代码} 最新股价`
- `{股票名} {股票代码} 公告 巨潮资讯`
- `{股票名} {股票代码} 年报 半年报 季报`
- `{股票名} 投资者关系 活动记录`
- `{股票名} {主题} 互动易`
- `{主题} A股 产业链 受益股`
- `{global catalyst} IPO filing latest official`

## Evidence Labels

Use these labels in answers when helpful:

- `已验证`: official disclosure, exchange/regulator, or company source.
- `程序拉取`: generated from local scripts using AkShare/Eastmoney/THS/Sina sources; include date and source.
- `高可信`: reputable media with named dates and detailed reporting.
- `待验证`: article summaries, market rumors, stock forum content, or unsourced claims.
- `情绪线索`: investor sentiment, forum heat, repeated market narrative.
