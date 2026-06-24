---
name: company-disclosure-watch
description: Use this skill to find, verify, and analyze company disclosures, including A-share announcements, 巨潮资讯 filings, exchange notices, annual/interim/quarterly reports, investor relations records, SEC EDGAR filings, HKEX announcements, earnings releases, guidance, insider transactions, buybacks, offerings, litigation, pledges, reductions, customer contracts, and regulatory inquiries.
---

# Company Disclosure Watch

## Core Rule

Prefer official filings over media summaries. For current filings or disclosure-sensitive questions, verify directly from the relevant filing source and cite the filing date, filing type, company name, ticker, and reporting period.

Distinguish:

- Filed fact: directly stated in a filing or exchange announcement.
- Management claim: guidance, outlook, investor-relations answer, conference-call statement.
- Media interpretation: article summary or analyst framing.
- Market rumor: unverified claim.

## Source Priority

Use the source map in `references/disclosure-sources.md` for search patterns and official portals.

Priority order:

1. Official filing portals: 巨潮资讯, 上交所, 深交所, 北交所, SEC EDGAR, HKEXnews.
2. Company investor relations and press releases.
3. Exchange/regulator letters and disciplinary records.
4. Earnings-call transcripts and presentation decks.
5. Reputable media summaries only after official filings are checked.

## Workflow

1. Normalize identifiers: company name, ticker, exchange, market, CIK if US-listed, stock code if A-share/HK.
2. Find the latest relevant filing by date and type.
3. Extract the exact disclosure item:
   - Earnings: revenue, net income, margin, cash flow, guidance, segment results.
   - Risk: litigation, inquiry letter, penalty, delisting risk, pledge, guarantee, impairment.
   - Capital action: buyback, placement, convertible bond, dividend, lock-up expiry, shareholder reduction.
   - Business catalyst: contract, order, customer, capacity, certification, regulatory approval, M&A.
4. Compare against prior periods or prior announcements when the user asks for change or surprise.
5. State what is not disclosed. Do not infer orders, customers, revenue contribution, or production scale unless the filing states it.

## Output

Use this structure:

- Filing found: company, ticker, filing type, date, period, source.
- Key disclosure: concise facts and numbers.
- What changed: versus prior filing or guidance if available.
- Market relevance: earnings, balance sheet, governance, regulation, catalyst, or risk.
- Open questions: facts not disclosed or needing follow-up.
- Reliability: official/high/media/rumor.

