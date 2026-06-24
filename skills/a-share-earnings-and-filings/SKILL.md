---
name: a-share-earnings-and-filings
description: Use this skill for A-share company filings and financial reports, including annual reports, interim reports, quarterly reports, performance previews, announcements, inquiry letters,监管函,减持,回购,定增,可转债,分红,质押,诉讼,订单,合同, and investor-relations activity records. Trigger when the user asks about A股财报, 公告, 业绩预告, 问询函, 监管函, 巨潮资讯, 互动易, 投资者关系, or company fundamentals.
---

# A-Share Earnings And Filings

## Core Rule

Use official filings first: 巨潮资讯, 上交所, 深交所, 北交所, company IR, and regulator/exchange notices. Cite filing type, date, period, and source. Avoid relying only on media summaries.

Separate:

- Filed fact: directly disclosed in an announcement/report.
- Management statement: IR activity record, performance meeting, investor Q&A.
- Inference: your analysis of trend, quality, risk, or valuation.

## Workflow

1. Normalize company name and stock code.
2. Find the latest relevant filing and confirm report period.
3. Extract:
   - Revenue, net profit,扣非净利润
   - Gross margin, net margin
   - Operating cash flow
   - Inventory, receivables, capex, R&D
   - Debt, pledge, guarantees, impairments
   - Orders, contracts, capacity, customers if disclosed
4. Compare YoY, QoQ, and prior guidance where available.
5. Check quality:
   - Profit supported by cash flow?
   - Receivables/inventory rising faster than revenue?
   - One-off gains or impairment?
   - Major customer/supplier concentration?
6. Identify the most important bull point, bear point, and follow-up data.

## Output

Use this structure:

- Filing found: company, code, filing type, date, period.
- Key numbers: concise table or bullets.
- Quality check: cash flow, margins, inventory, receivables, debt.
- What changed: versus prior period/guidance.
- Market implication: catalyst or risk.
- Follow-up: disclosures still needed.

