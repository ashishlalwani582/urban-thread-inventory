# Step 1-3: Persona, assumptions, signals

## Persona
**Meera, Regional Inventory Planner** at "Urban Thread", a 24-store apparel retailer (West, North, South, East).
Her Monday: opens 3 reports, exports to Excel, eyeballs sell-through. By the time she finds a stockout on a fast
mover, the store has been empty for a week. By the time she spots dead stock, the season is half gone and the
markdown has to be deeper.

**Her real question:** "What do I need to act on *today*, what should I do, and what will it cost me if I wait?"

## Assumptions (stated up front, as the brief asks)
1. 24 stores, 1 central warehouse (DC), ~144 SKUs (36 styles x 4 sizes), 6 categories.
2. Data refreshed daily; velocity = average daily units sold over the last 28 days.
3. Replenishment from DC takes 5 days (lead time); store-to-store transfer takes 2 (same region) or 4 days (cross-region).
4. Transfer cost: Rs 18/unit same region, Rs 45/unit cross region. Replenishment ships in pack sizes of 6.
5. Target cover: 30 days. Overstock: > 90 days of cover. Dead: no sale in 60+ days.
6. Markdown never goes below cost + 10% margin without manager sign-off.
7. A store with < 28 days of history is "new": its numbers are shown but flagged low-confidence.

## Signals (6 chosen, 3 deliberately dropped)
| Signal | Why it matters | Rule |
|---|---|---|
| Days of cover | the universal health number | (on hand + in transit) / velocity |
| Stockout risk | lost sales are invisible | cover < lead time + 3 days and velocity is meaningful |
| Overstock | cash locked in stock | cover > 90 days |
| Dead stock | markdown urgency | no sale 60+ days |
| Broken size curve | a style "in stock" but unsellable | <= 2 of 4 sizes available in a store |
| Network imbalance | cheapest fix is often a transfer | store out of SKU while another has surplus |

**Dropped on purpose:** demand forecasting (trust in simple, explainable rules first), supplier OTIF scoring
(different persona), price elasticity modelling (needs more data than we can assume).

## Insight -> action flow
Alert -> Why it was flagged -> Recommended action (replenish / transfer / markdown) -> Approve, edit or reject -> Tracker with impact.

## Edge cases handled in the prototype
- New store / low history -> low-confidence flag, no auto-recommendation
- Negative stock (data error) -> excluded from recommendations, listed under data quality
- Promo distorting velocity -> flagged, recommendation uses a discounted velocity
- Stock in transit -> counted in cover, so we don't replenish twice
- Pack size / MOQ -> replenish qty rounded up to packs of 6
- Warehouse shortfall -> recommendation capped and flagged
- Two stores wanting the same surplus -> donor surplus allocated once, most urgent first
- Markdown margin floor -> capped, and flagged for approval
