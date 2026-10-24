import pandas as pd
import plotly.express as px
import streamlit as st

import engine

st.set_page_config(page_title="Urban Thread | Inventory Intelligence", layout="wide")


@st.cache_data
def get_data():
    df, dc = engine.load()
    sig = engine.compute_signals(df)
    return sig, dc, engine.recommend(sig, dc)


sig, dc, recs = get_data()

# ---- session state: the tracker lives here ----
if "status" not in st.session_state:
    st.session_state.status = {}      # id -> Pending / Approved / Rejected
    st.session_state.edits = {}       # id -> edited qty
    st.session_state.notes = {}       # id -> reject reason
    st.session_state.selected = None
recs["status"] = recs.id.map(lambda i: st.session_state.status.get(i, "Pending"))
recs["final_qty"] = [st.session_state.edits.get(i, q) for i, q in zip(recs.id, recs.qty)]

inr = lambda x: f"Rs {x:,.0f}"

st.sidebar.title("Urban Thread")
st.sidebar.caption("Regional Inventory Planner view: Meera")
page = st.sidebar.radio("Go to", ["1. Network overview", "2. Risk drill-down", "3. Act on recommendations", "4. Action tracker", "About this prototype"])
region = st.sidebar.multiselect("Region", sorted(sig.region.unique()), default=sorted(sig.region.unique()))
st.sidebar.caption("Data: simulated, refreshed daily. Velocity = avg daily sales, last 28 days.")

view = sig[sig.region.isin(region)]
vrecs = recs[recs.region.isin(region)]

# ====================================================================
if page.startswith("1"):
    st.title("What needs attention today")
    pending = vrecs[vrecs.status == "Pending"]
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Lines at stockout risk", int(view.stockout_risk.sum()), help="Cover shorter than DC lead time + 3 days")
    c2.metric("Sales at risk (next cycle)", inr(view.lost_sales_risk.sum()))
    c3.metric("Cash in dead stock", inr(view[view.dead].stock_value.sum()), help="60+ days with no sale, cost value")
    c4.metric("Actions waiting on you", len(pending))

    st.subheader("Top 5 things to do now")
    # mix of action types so one noisy category doesn't crowd out stockouts
    top = pending.groupby('action', group_keys=False).head(2).sort_values('value_at_risk', ascending=False).head(5)
    for r in top.itertuples():
        with st.container(border=True):
            a, b, c = st.columns([5, 2, 1])
            a.markdown(f"**{r.action}**: {r.style} ({r.size}) at **{r.store}**  \n{r.signal} - {r.reason.split(';')[0]}")
            b.markdown(f"At risk: **{inr(r.value_at_risk)}**  \nConfidence: {r.confidence}")
            if c.button("Review", key=f"rv{r.id}"):
                st.session_state.selected = r.id
                st.info("Open '3. Act on recommendations' in the sidebar: this action is pre-selected.")

    st.subheader("Where is the risk? (store x category)")
    h = view.groupby(["store", "category"]).agg(risk=("lost_sales_risk", "sum"), dead=("stock_value", lambda s: 0)).reset_index()
    over = view[view.dead | view.overstock].groupby(["store", "category"]).stock_value.sum().rename("locked").reset_index()
    h = h.merge(over, how="left", on=["store", "category"]).fillna(0)
    metric = st.radio("Show", ["Sales at risk (stockouts)", "Cash locked (overstock + dead)"], horizontal=True)
    col, title = ("risk", "Sales at risk") if metric.startswith("Sales") else ("locked", "Cash locked")
    pivot = h.pivot(index="store", columns="category", values=col).fillna(0)
    fig = px.imshow(pivot, aspect="auto", color_continuous_scale="Reds", labels=dict(color=title))
    st.plotly_chart(fig, width='stretch')

    st.subheader("Store health")
    sh = engine.store_health(view).sort_values("lost_sales_risk", ascending=False)
    sh["stock_value"] = sh.stock_value.round(0)
    sh["lost_sales_risk"] = sh.lost_sales_risk.round(0)
    st.dataframe(sh, width='stretch', hide_index=True)

    dq = engine.data_quality(view)
    if len(dq):
        with st.expander(f"Data quality: {len(dq)} lines excluded"):
            st.caption("We'd rather skip a line than recommend off a wrong number.")
            st.dataframe(dq, hide_index=True, width='stretch')

# ====================================================================
elif page.startswith("2"):
    st.title("Risk drill-down")
    f1, f2, f3 = st.columns(3)
    stores = f1.multiselect("Store", sorted(view.store.unique()))
    cats = f2.multiselect("Category", sorted(view.category.unique()))
    sigs = f3.multiselect("Signal", ["Stockout risk", "Overstock", "Dead stock", "Broken size curve"], default=["Stockout risk"])
    d = view.copy()
    if stores: d = d[d.store.isin(stores)]
    if cats: d = d[d.category.isin(cats)]
    mask = pd.Series(False, index=d.index)
    for s_, col in [("Stockout risk", "stockout_risk"), ("Overstock", "overstock"), ("Dead stock", "dead"), ("Broken size curve", "broken_curve")]:
        if s_ in sigs: mask |= d[col]
    d = d[mask].copy()
    def label(r):
        l = [n for n, c in [("Stockout", r.stockout_risk), ("Overstock", r.overstock), ("Dead", r.dead), ("Broken curve", r.broken_curve)] if c]
        return ", ".join(l)
    d["signals"] = d.apply(label, axis=1)
    d["note"] = d.apply(lambda r: "New store: low confidence" if r.low_history else ("Promo-inflated" if r.on_promo else ""), axis=1)
    st.caption(f"{len(d)} lines match. Sorted by sales at risk, then cash locked.")
    cols = ["store", "style", "size", "on_hand", "in_transit", "plan_velocity", "cover_days", "last_sale_days", "signals", "lost_sales_risk", "stock_value", "note"]
    st.dataframe(d.sort_values(["lost_sales_risk", "stock_value"], ascending=False)[cols], width='stretch', hide_index=True,
                 column_config={"cover_days": st.column_config.NumberColumn("Days cover", help="(on hand + in transit) / daily velocity; 999 = no sales")})
    st.markdown("**Reading this table:** 'Days cover' is the number to trust. 'Note' tells you when not to trust it blindly.")

# ====================================================================
elif page.startswith("3"):
    st.title("Act on recommendations")
    st.caption("Every recommendation says *why*. You can edit the quantity or reject it with a reason.")
    t1, t2, t3, t4 = st.columns(4)
    atype = t1.selectbox("Action type", ["All", "Replenish", "Transfer", "Markdown", "Escalate"])
    conf = t2.selectbox("Confidence", ["All", "High", "Medium", "Low"])
    only_pending = t3.checkbox("Pending only", value=True)
    warn_only = t4.checkbox("With warnings only")
    d = vrecs.copy()
    if atype != "All": d = d[d.action == atype]
    if conf != "All": d = d[d.confidence == conf]
    if only_pending: d = d[d.status == "Pending"]
    if warn_only: d = d[d.warnings != ""]
    if st.session_state.selected and st.session_state.selected in set(d.id):
        sel = d[d.id == st.session_state.selected]
        d = pd.concat([sel, d[d.id != st.session_state.selected]])
    st.caption(f"{len(d)} actions")

    for r in d.head(15).itertuples():
        with st.container(border=True):
            top_l, top_r = st.columns([4, 1])
            top_l.markdown(f"### {r.action}: {r.style} ({r.size}) -> {r.store}")
            top_r.markdown(f"**{r.status}**")
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Quantity", r.final_qty)
            m2.metric("From" if r.action != "Markdown" else "Price", r.source)
            m3.metric("Cost to act / ETA", f"{inr(r.cost_to_act)} / {r.eta_days}d" if r.action != "Markdown" else "-")
            m4.metric("At risk if we wait", inr(r.value_at_risk))
            st.markdown(f"**Why:** {r.reason}")
            if r.warnings: st.warning(r.warnings)
            if r.confidence != "High": st.caption(f"Confidence: {r.confidence}")
            if r.status == "Pending":
                q = st.number_input("Edit quantity", min_value=0, value=int(r.final_qty), step=1, key=f"q{r.id}")
                b1, b2, b3 = st.columns([1, 1, 3])
                if b1.button("Approve", key=f"ap{r.id}", type="primary"):
                    st.session_state.edits[r.id] = int(q); st.session_state.status[r.id] = "Approved"; st.rerun()
                reason = b3.selectbox("Reject reason", ["", "Already handled", "Store has local info", "Disagree with demand", "Bad data"], key=f"rs{r.id}", label_visibility="collapsed")
                if b2.button("Reject", key=f"rj{r.id}"):
                    st.session_state.status[r.id] = "Rejected"; st.session_state.notes[r.id] = reason or "No reason"; st.rerun()

# ====================================================================
elif page.startswith("4"):
    st.title("Action tracker")
    done = vrecs[vrecs.status != "Pending"]
    appr = done[done.status == "Approved"]
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Approved", len(appr))
    c2.metric("Rejected", int((done.status == "Rejected").sum()))
    c3.metric("Sales protected (est.)", inr(appr[appr.action.isin(["Replenish", "Transfer"])].value_at_risk.sum()))
    c4.metric("Cost to execute", inr(appr.cost_to_act.sum()))
    if done.empty:
        st.info("Nothing here yet. Approve or reject something in '3. Act on recommendations'.")
    else:
        t = done[["id", "action", "store", "style", "size", "final_qty", "source", "cost_to_act", "value_at_risk", "status"]].copy()
        t["reject_reason"] = t.id.map(st.session_state.notes).fillna("")
        st.dataframe(t, width='stretch', hide_index=True)
        st.caption("Rejection reasons are the feedback loop: if many say 'Disagree with demand', the rules need tuning, not the planner.")
        if st.button("Reset demo"):
            for k in ("status", "edits", "notes"): st.session_state[k] = {}
            st.session_state.selected = None; st.rerun()

# ====================================================================
else:
    st.title("About this prototype")
    st.markdown(open("docs/01_thinking.md").read())
