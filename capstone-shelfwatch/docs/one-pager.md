# ShelfWatch: one-pager

**Problem (3 sentences).** Small online book resellers set their prices by hand, by opening a competitor's site and
checking titles one by one. With a catalogue of even 60 titles that is about an hour of clicking every week, so it gets done
rarely and price drops or stock-outs are noticed days late. They lose sales to a cheaper competitor without knowing it.

**Who has it.** One-person or small-team online sellers (books first; the same pattern fits any catalogue) who have no
data team and no budget for paid price-tracking tools.

**10x claim.** A full check of a 60-title competitor catalogue takes a person ~60 minutes; ShelfWatch does it unattended
every morning in ~1 minute, records every price and stock change, and hands over a one-page PDF brief. That's 60× less
time, plus changes are seen the same day instead of next week.

**Concepts (7 core, 0 swaps).**
1. API endpoints with validation and correct status codes
2. Database (SQLite) with price history that survives restarts
3. Authentication (sign up / log in, JWT-protected API)
4. Background jobs (scans run after a 202) + cron (daily scan, weekly report)
5. Reporting: weekly PDF brief
6. Caching: page cache (politeness) + a TTL cache for dashboard stats + LLM results cached by content hash
7. LLM integration: one narrow job, categorising each new title from a closed list, schema-validated, cost-logged

(Bonus, not counted: the polite web-scraping pipeline from BE-05 is the data source.)

**Non-goal.** No automatic re-pricing of the seller's own shop. ShelfWatch tells you what changed; a human decides the price.

**Feature list (scope guard, 5 features).**
1. Watch a catalogue: start a scan, get every title's price/stock, detect changes
2. Browse titles, price history and a change feed
3. AI category for every new title
4. Weekly PDF brief
5. Accounts: only signed-in users can use the API
