"""Signal detection + recommendation logic. Plain rules on purpose: explainable beats clever."""
import numpy as np
import pandas as pd

LEAD_DC = 5
LEAD_TRANSFER = {"same": 2, "cross": 4}
TRANSFER_COST = {"same": 18, "cross": 45}
TARGET_COVER = 30
OVERSTOCK_COVER = 90
DEAD_DAYS = 60
MIN_VELOCITY = 0.15       # below this, a "stockout" isn't worth alerting on
PACK = 6
MARGIN_FLOOR = 1.10       # never mark down below cost * 1.10 without sign-off
NEW_STORE_DAYS = 28
EXTRA_MARKDOWN_IF_WAIT = 0.25  # assumption: waiting a month costs ~25% of cost value in deeper markdowns
PROMO_DISCOUNT = 0.55     # on-promo velocity is trimmed to this share when planning


def load(inv_path="data/store_inventory.csv", dc_path="data/warehouse_stock.csv"):
    return pd.read_csv(inv_path), pd.read_csv(dc_path)


def compute_signals(df):
    d = df.copy()
    d["bad_data"] = d.on_hand < 0
    d["low_history"] = d.history_days < NEW_STORE_DAYS
    # Promo inflates velocity, so plan on a trimmed number
    d["plan_velocity"] = np.where(d.on_promo, d.velocity * PROMO_DISCOUNT, d.velocity)
    avail = d.on_hand.clip(lower=0) + d.in_transit
    d["cover_days"] = np.minimum(np.where(d.plan_velocity > 0, avail / d.plan_velocity.replace(0, np.nan), 999), 365).round(1)
    d["stockout_risk"] = (~d.bad_data) & (d.plan_velocity >= MIN_VELOCITY) & (d.cover_days < LEAD_DC + 3)
    d["overstock"] = (~d.bad_data) & (d.cover_days > OVERSTOCK_COVER) & (d.on_hand > 6)
    d["dead"] = (~d.bad_data) & (d.last_sale_days >= DEAD_DAYS) & (d.on_hand >= 8)
    d["stock_value"] = d.on_hand.clip(lower=0) * d.cost

    # broken size curve: style sold recently in this store but <=2 of 4 sizes available
    g = d.groupby(["store", "style"])
    d["sizes_avail"] = g.on_hand.transform(lambda s: (s > 0).sum())
    d["style_velocity"] = g.plan_velocity.transform("sum")
    d["broken_curve"] = (d.sizes_avail <= 2) & (d.style_velocity >= 0.6) & (d.on_hand <= 0) & (~d.bad_data)

    # lost sales exposure while we wait for replenishment
    gap = (LEAD_DC - d.cover_days).clip(lower=0)
    d["lost_sales_risk"] = np.where(d.stockout_risk, d.plan_velocity * gap * d.mrp + d.plan_velocity * 7 * d.mrp * 0.5, 0).round(0)
    return d


def recommend(sig, dc):
    """Return one recommended action per flagged store-SKU. Donor surplus and DC stock are allocated once."""
    dc_left = dc.set_index("sku").dc_stock.to_dict()
    sig = sig.copy()
    # surplus a store can give away while keeping TARGET_COVER
    sig["surplus"] = np.where(
        (~sig.bad_data) & (sig.cover_days > OVERSTOCK_COVER * 0.75),
        (sig.on_hand - np.ceil(sig.plan_velocity * TARGET_COVER)).clip(lower=0), 0).astype(int)
    donors = {}
    for r in sig[sig.surplus > 0].itertuples():
        donors.setdefault(r.sku, []).append([r.store, r.region, r.surplus, r.cover_days])

    recs = []
    need = sig[(sig.stockout_risk | sig.broken_curve) & (~sig.bad_data)].sort_values("lost_sales_risk", ascending=False)
    for r in need.itertuples():
        want = int(np.ceil(max(r.plan_velocity, 0.2) * TARGET_COVER) - (max(r.on_hand, 0) + r.in_transit))
        want = max(want, 1)
        reason_bits = [f"{max(r.on_hand,0)} on hand, {r.in_transit} in transit, selling {r.plan_velocity:.2f}/day -> {r.cover_days:.0f} days cover"]
        if r.broken_curve:
            reason_bits.append(f"size curve broken ({r.sizes_avail}/4 sizes of '{r.style}' in store)")
        if r.on_promo:
            reason_bits.append("promo running: velocity trimmed for planning")
        conf = "Low" if r.low_history else ("Medium" if r.on_promo else "High")
        if r.low_history:
            reason_bits.append(f"new store ({r.history_days} days of history): treat as indicative")

        # 1) try a transfer first: cheaper and faster when a donor exists
        action, qty, src, cost, days, flags = None, 0, "", 0.0, 0, []
        cands = sorted(donors.get(r.sku, []), key=lambda x: (x[1] != r.region, -x[2]))
        for c in cands:
            if c[2] >= max(3, want // 2) and c[0] != r.store:
                typ = "same" if c[1] == r.region else "cross"
                qty = int(min(want, c[2]))
                c[2] -= qty
                action, src, cost, days = "Transfer", c[0], qty * TRANSFER_COST[typ], LEAD_TRANSFER[typ]
                reason_bits.append(f"{src} has surplus ({c[3]:.0f} days cover); {typ}-region transfer is {days}d vs {LEAD_DC}d from DC")
                break
        # 2) otherwise replenish from DC in pack sizes, capped by DC stock
        if action is None:
            avail_dc = dc_left.get(r.sku, 0)
            qty = int(np.ceil(want / PACK) * PACK)
            if avail_dc < qty:
                flags.append(f"DC short: needs {qty}, has {avail_dc}")
                qty = int(avail_dc // PACK * PACK) if avail_dc >= PACK else int(avail_dc)
            dc_left[r.sku] = avail_dc - qty
            action, src, cost, days = "Replenish", "Central DC", qty * 4, LEAD_DC
            if qty == 0:
                action, src = "Escalate", "Buying team"
                flags.append("No DC stock: raise a PO / check alternate sizes")
        if r.on_promo:
            flags.append("Promo-inflated demand")
        recs.append(dict(
            id=f"A{len(recs)+1:03d}", action=action, store=r.store, region=r.region, sku=r.sku, style=r.style,
            category=r.category, size=r.size, qty=qty, source=src, cost_to_act=round(cost), eta_days=days,
            value_at_risk=r.lost_sales_risk, confidence=conf, reason="; ".join(reason_bits), warnings="; ".join(flags),
            cover_days=r.cover_days, signal="Broken size curve" if r.broken_curve and not r.stockout_risk else "Stockout risk"))

    # markdowns for dead / overstock lines
    over = sig[(sig.dead | sig.overstock) & (~sig.bad_data)].copy()
    over["value"] = over.stock_value
    for r in over.sort_values("value", ascending=False).head(30).itertuples():
        # leftover surplus that wasn't used by a transfer
        left = next((c[2] for c in donors.get(r.sku, []) if c[0] == r.store), r.surplus)
        if left <= 0 and not r.dead:
            continue
        pct = 0.40 if r.last_sale_days >= 90 else 0.30 if r.last_sale_days >= DEAD_DAYS else 0.20
        floor_price = r.cost * MARGIN_FLOOR
        price = max(round(r.mrp * (1 - pct)), round(floor_price))
        capped = price == round(floor_price) and r.mrp * (1 - pct) < floor_price
        flags = ["Margin floor hit: needs manager sign-off"] if capped else []
        eff_pct = round((1 - price / r.mrp) * 100)
        why = (f"{r.on_hand} units, {'no sale in ' + str(r.last_sale_days) + ' days' if r.dead else f'{r.cover_days:.0f} days cover'}; "
               f"Rs {r.on_hand * r.cost:,.0f} of cost locked up")
        recs.append(dict(
            id=f"A{len(recs)+1:03d}", action="Markdown", store=r.store, region=r.region, sku=r.sku, style=r.style,
            category=r.category, size=r.size, qty=int(r.on_hand), source=f"{eff_pct}% off (to Rs {price})", cost_to_act=0, eta_days=0,
            value_at_risk=float(r.on_hand * r.cost * EXTRA_MARKDOWN_IF_WAIT), confidence="High" if r.history_days >= NEW_STORE_DAYS else "Low",
            reason=why, warnings="; ".join(flags), cover_days=r.cover_days, signal="Dead stock" if r.dead else "Overstock"))
    out = pd.DataFrame(recs)
    out["priority"] = out.value_at_risk.rank(pct=True).round(2)
    return out.sort_values("value_at_risk", ascending=False).reset_index(drop=True)


def data_quality(sig):
    q = sig[sig.bad_data][["store", "sku", "style", "size", "on_hand"]].copy()
    q["issue"] = "Negative stock on hand: excluded from recommendations"
    return q


def store_health(sig):
    g = sig.groupby(["store", "region"])
    h = g.agg(stockout_lines=("stockout_risk", "sum"), overstock_lines=("overstock", "sum"),
              dead_lines=("dead", "sum"), stock_value=("stock_value", "sum"),
              lost_sales_risk=("lost_sales_risk", "sum")).reset_index()
    return h
