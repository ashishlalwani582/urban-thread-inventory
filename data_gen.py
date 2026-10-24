"""Generates a realistic-looking retail dataset with deliberately planted problems."""
import numpy as np
import pandas as pd

rng = np.random.default_rng(42)

STORES = [
    ("Mumbai - Andheri", "West"), ("Mumbai - Bandra", "West"), ("Pune - Koregaon Park", "West"),
    ("Pune - Hinjewadi", "West"), ("Ahmedabad - CG Road", "West"), ("Surat - Vesu", "West"),
    ("Delhi - Saket", "North"), ("Delhi - Rajouri", "North"), ("Gurgaon - Ambience", "North"),
    ("Noida - Sector 18", "North"), ("Jaipur - MI Road", "North"), ("Chandigarh - Sec 17", "North"),
    ("Bengaluru - Indiranagar", "South"), ("Bengaluru - Koramangala", "South"), ("Chennai - T Nagar", "South"),
    ("Hyderabad - Banjara", "South"), ("Kochi - Lulu", "South"), ("Coimbatore - RS Puram", "South"),
    ("Kolkata - Park Street", "East"), ("Kolkata - Salt Lake", "East"), ("Bhubaneswar - Patia", "East"),
    ("Guwahati - GS Road", "East"), ("Patna - Boring Road", "East"), ("Ranchi - Main Rd", "East"),
]
NEW_STORES = {"Hyderabad - Banjara": 12, "Kochi - Lulu": 20}  # days since opening

CATEGORIES = {
    "Shirts": (1299, 0.9), "Jeans": (1999, 0.7), "T-Shirts": (799, 1.3),
    "Kurtas": (1499, 0.8), "Jackets": (2999, 0.35), "Dresses": (1799, 0.6),
}
STYLE_NAMES = {
    "Shirts": ["Navy Slim Oxford", "White Formal", "Check Casual", "Linen Sky", "Olive Utility", "Striped Classic"],
    "Jeans": ["Dark Indigo Straight", "Black Skinny", "Light Wash Relaxed", "Grey Tapered", "Mid Blue Slim", "Ripped Blue"],
    "T-Shirts": ["Plain Black Crew", "Graphic Retro", "Polo Maroon", "Henley Grey", "White Basic", "Pocket Olive"],
    "Kurtas": ["Mustard Cotton", "Indigo Block Print", "White Chikan", "Maroon Festive", "Teal Straight", "Rust Short"],
    "Jackets": ["Denim Trucker", "Bomber Olive", "Quilted Navy", "Faux Leather", "Windcheater Red", "Wool Blend Grey"],
    "Dresses": ["Floral Midi", "Black Wrap", "Linen Shirt Dress", "Polka Skater", "Maxi Emerald", "Denim Pinafore"],
}
SIZES = ["S", "M", "L", "XL"]
SIZE_WEIGHT = {"S": 0.2, "M": 0.35, "L": 0.3, "XL": 0.15}
REGION_FACTOR = {"Jackets": {"North": 1.8, "South": 0.4, "West": 0.8, "East": 0.7}}


def build():
    skus = []
    for cat, (mrp, base) in CATEGORIES.items():
        for i, style in enumerate(STYLE_NAMES[cat]):
            pop = float(rng.lognormal(0, 0.45))
            for sz in SIZES:
                skus.append(dict(
                    sku=f"{cat[:3].upper()}{i+1:02d}-{sz}", style=f"{style}", category=cat, size=sz,
                    mrp=mrp, cost=round(mrp * 0.45), popularity=base * pop * SIZE_WEIGHT[sz] * 4,
                    season="Core" if cat in ("Shirts", "Jeans", "T-Shirts") else "Seasonal",
                ))
    skus = pd.DataFrame(skus)

    rows = []
    for store, region in STORES:
        store_size = rng.uniform(0.7, 1.4)
        hist = NEW_STORES.get(store, 400)
        for _, s in skus.iterrows():
            rf = REGION_FACTOR.get(s.category, {}).get(region, 1.0)
            vel = max(0.0, rng.gamma(2.0, 0.5) * s.popularity * store_size * rf * 0.25)
            vel = round(vel, 2)
            on_hand = int(vel * rng.uniform(15, 70)) + int(rng.integers(0, 3))
            in_transit = int(rng.choice([0, 0, 0, 6, 12])) if vel > 0.3 else 0
            last_sale = int(rng.integers(0, 6)) if vel > 0.05 else int(rng.integers(20, 90))
            rows.append(dict(
                store=store, region=region, sku=s.sku, style=s["style"], category=s.category, size=s["size"],
                mrp=s.mrp, cost=s.cost, season=s.season, on_hand=on_hand, in_transit=in_transit,
                velocity=vel, last_sale_days=last_sale, receipt_age_days=int(rng.integers(10, 120)),
                history_days=hist, on_promo=False,
            ))
    df = pd.DataFrame(rows)

    # ---- planted problems (so the demo has a story) ----
    # 1. Fast movers stocked out in a few stores
    for store, cat in [("Mumbai - Bandra", "T-Shirts"), ("Delhi - Saket", "Jeans"), ("Bengaluru - Indiranagar", "Shirts"),
                       ("Pune - Koregaon Park", "Dresses")]:
        m = (df.store == store) & (df.category == cat) & (df["size"].isin(["M", "L"]))
        df.loc[m, "on_hand"] = rng.integers(0, 2, m.sum())
        df.loc[m, "velocity"] = (df.loc[m, "velocity"] * 1.8).round(2).clip(lower=0.6)
    # 2. Jackets overstocked in the South (wrong season/region), dead in Chennai
    m = (df.category == "Jackets") & (df.region == "South")
    df.loc[m, "on_hand"] = rng.integers(25, 60, m.sum())
    df.loc[m & (df.store == "Chennai - T Nagar"), ["velocity", "last_sale_days"]] = [0.02, 75]
    # 3. Broken size curves: Kurtas in two stores, only S and XL left
    for store in ["Jaipur - MI Road", "Kolkata - Park Street"]:
        m = (df.store == store) & (df.category == "Kurtas") & (df["size"].isin(["M", "L"]))
        df.loc[m, "on_hand"] = 0
    # 4. Donor surplus: North has excess jeans (can feed Delhi - Saket)
    m = (df.store.isin(["Gurgaon - Ambience", "Noida - Sector 18"])) & (df.category == "Jeans") & (df.store != "Delhi - Saket")
    df.loc[m, "on_hand"] = (df.loc[m, "on_hand"] * 3 + 20)
    # 5. Data quality: negative stock
    bad = df.sample(6, random_state=3).index
    df.loc[bad, "on_hand"] = -rng.integers(1, 5, len(bad))
    # 6. Promo distorting velocity
    m = (df.category == "Shirts") & (df.store.isin(["Surat - Vesu", "Ahmedabad - CG Road"]))
    df.loc[m, "on_promo"] = True
    df.loc[m, "velocity"] = (df.loc[m, "velocity"] * 2.2).round(2)
    # 7. Dead stock scattered
    dead = df[df.category.isin(["Jackets", "Dresses"])].sample(40, random_state=7).index
    df.loc[dead, "velocity"] = 0.0
    df.loc[dead, "last_sale_days"] = rng.integers(62, 150, len(dead))
    df.loc[dead, "on_hand"] = rng.integers(8, 30, len(dead))

    # Warehouse stock per SKU (some intentionally short)
    dc = skus[["sku"]].copy()
    dc["dc_stock"] = rng.integers(30, 400, len(dc))
    short = dc.sku.str.startswith("JEA") & dc.sku.str.endswith(("M", "L"))
    dc.loc[short, "dc_stock"] = rng.integers(0, 14, int(short.sum()))
    return df, dc


if __name__ == "__main__":
    df, dc = build()
    df.to_csv("data/store_inventory.csv", index=False)
    dc.to_csv("data/warehouse_stock.csv", index=False)
    print(len(df), "store-sku rows,", len(dc), "warehouse rows")
