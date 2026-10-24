# Product brief: 7-slide skeleton (write the sentences yourself)
Rule: every slide has facts from the prototype + a line marked YOU that only you can write. Use "I", not "we".

**1. The problem (Meera's Monday)**
Facts: 24 stores, fragmented reports, decisions made a week late. YOU: one real moment you've seen in retail, e.g. a store
out of a bestselling size while another store sits on 60 of it. Why does this hurt? (lost sales + cash locked)

**2. Who I'm building for + assumptions**
Facts: persona Meera; assumptions list in docs/01_thinking.md. YOU: which assumption are you least sure about, and what
would you ask a real customer to validate it?

**3. Signals: what I chose and what I dropped**
Facts: 6 signals, 3 dropped (forecasting, supplier OTIF, elasticity). YOU: why did you drop forecasting? (suggested angle: trust
before sophistication; planners won't act on numbers they can't explain)

**4. Insight to action flow (screenshot: screens 1 and 3)**
Facts: alert -> why -> replenish / transfer / markdown -> approve / edit / reject -> tracker.
YOU: why transfer is tried before replenish (cheaper, faster, frees dead cash) and why every card shows a "Why".

**5. Edge cases I handled (table)**
New store, negative stock, promo-inflated velocity, in-transit, pack size, DC shortfall, donor surplus allocated once,
margin floor on markdowns. YOU: pick the one you're proudest of and say what you'd get wrong if you ignored it.

**6. Key decisions and trade-offs**
- Rules over ML. - Recommend, never auto-execute (planner approves). - Rejection reasons captured as feedback.
- Excluded bad data instead of guessing. YOU: one decision you went back and forth on.

**7. Success metrics + what's next**
Metrics: stockout days per store, % cash in 90+ day stock, time from alert to action, % recommendations accepted.
Next: integrate with Ginesys ERP stock/PO data, multi-day trend, role-based views, forecast layer once rules are trusted.
YOU: what you'd do with another week, and what you're unsure about.

# 2-3 minute demo recording script
1. (20s) Overview: "Meera opens this on Monday. 57 lines at risk, Rs 4.2 lakh of sales exposed."
2. (30s) Top 5: click Review on a stockout, e.g. Bengaluru Indiranagar Check Casual M.
3. (45s) Act screen: read the Why, edit the qty, approve. Then show a transfer and point out the cheaper/faster comparison.
4. (30s) Show a warning card (DC short or promo-inflated) and reject one with a reason.
5. (20s) Tracker: sales protected and cost to execute. Mention rejection reasons as feedback.
6. (15s) Data quality expander: "I'd rather skip a line than recommend off a wrong number."

# Share it
Streamlit Community Cloud: push this folder to a GitHub repo, then share.streamlit.io -> New app -> app.py. Paste the link in your submission.
