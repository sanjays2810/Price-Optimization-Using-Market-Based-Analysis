"""Analytics: dashboard, EDA, trends, demand/supply, competitors, profit. Every number is computed from the DataFrame."""
import calendar

import numpy as np
import pandas as pd
from scipy import stats
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import StandardScaler

from app.ml import predictor

NUM_COLS = ["historical_price", "cost_price", "selling_price", "demand_qty", "supply_qty",
            "competitor_price", "sales_qty", "inventory"]
TREND_LABELS = {"increasing": "Bullish (Increasing)", "decreasing": "Bearish (Decreasing)", "stable": "Stable"}


# ------------------------------------------------------------------ helpers
def scope(df, product_id=None, category=None):
    if product_id:
        df = df[df.product_id == int(product_id)]
    if category and category != "all":
        df = df[df.category == category]
    return df


def daily(df, col, agg="mean"):
    s = df.groupby("date")[col].agg(agg).asfreq("D")
    return s.interpolate(limit_direction="both")


def growth(s, days=30):
    if len(s) < 2 * days:
        days = max(len(s) // 2, 1)
    last, prev = s.iloc[-days:].mean(), s.iloc[-2 * days:-days].mean()
    return float((last - prev) / prev * 100) if prev else 0.0


def with_money(df):
    d = df.copy()
    d["revenue"] = d.selling_price * d.sales_qty
    d["total_cost"] = d.cost_price * d.sales_qty
    d["profit"] = d.revenue - d.total_cost
    return d


def _margin(profit, revenue):
    return float(profit / revenue * 100) if revenue else 0.0


def classify_trend(s):
    rec = s.iloc[-90:]
    y = np.log(rec.clip(lower=1e-9).values)
    lr = stats.linregress(np.arange(len(y)), y)
    monthly = (np.exp(lr.slope * 30) - 1) * 100
    if lr.pvalue < 0.05 and monthly >= 1.5:
        key = "increasing"
    elif lr.pvalue < 0.05 and monthly <= -1.5:
        key = "decreasing"
    else:
        key = "stable"
    return key, float(monthly), float(lr.pvalue)


def seasonal_info(s):
    if len(s) < 400:
        return {"seasonal": False, "strength": 0.0}
    t = np.arange(len(s))
    logs = np.log(s.clip(lower=1e-9).values)
    detr = logs - np.polyval(np.polyfit(t, logs, 1), t)
    month_means = pd.Series(detr, index=s.index).groupby(s.index.month).mean()
    strength = float(month_means.reindex(s.index.month).var() / np.var(detr)) if np.var(detr) > 0 else 0.0
    return {"seasonal": strength > 0.25, "strength": strength,
            "peak_month": calendar.month_name[int(month_means.idxmax())],
            "trough_month": calendar.month_name[int(month_means.idxmin())]}


def explain(g, s, trend_key):
    dem, sup, comp = daily(g, "demand_qty"), daily(g, "supply_qty"), daily(g, "competitor_price")
    pg, dg, sg, cg = growth(s), growth(dem), growth(sup), growth(comp)
    out = [f"Market price moved {pg:+.1f}% (last 30 days vs the previous 30 days).",
           f"Over the same period demand changed {dg:+.1f}% and supply changed {sg:+.1f}%."]
    if dg > 2 and sg < -2:
        out.append("Rising demand with falling supply is consistent with upward price pressure.")
    elif dg < -2 and sg > 2:
        out.append("Falling demand with rising supply is consistent with downward price pressure.")
    elif dg > 2 and sg > 2:
        out.append("Demand and supply are both rising: a balanced, competitive market where price changes tend to stay modest.")
    elif dg < -2 and sg < -2:
        out.append("Demand and supply are both falling: low market activity.")
    else:
        out.append("Demand and supply are broadly steady, so they explain little of the recent price movement.")
    if abs(cg - pg) > 3:
        out.append(f"Competitor prices moved {cg:+.1f}%, noticeably different from the market price ({pg:+.1f}%).")
    si = seasonal_info(s)
    if si["seasonal"]:
        out.append(f"Prices follow a seasonal pattern, usually peaking around {si['peak_month']} and bottoming around {si['trough_month']}.")
    out.append("These are statistical associations in the dataset, not proof of cause.")
    return out


def product_trends(df):
    rows = []
    for pid, g in df.groupby("product_id"):
        s = daily(g, "historical_price")
        if len(s) < 30:
            continue
        key, monthly, p = classify_trend(s)
        vol = float(s.pct_change().iloc[-90:].std() * 100)
        si = seasonal_info(s)
        rows.append({"product_id": int(pid), "product_name": g.product_name.iloc[0], "category": g.category.iloc[0],
                     "last_price": float(s.iloc[-7:].mean()), "change_7d": growth(s, 7), "change_30d": growth(s, 30),
                     "change_90d": growth(s, 90), "slope_pct_per_month": monthly, "p_value": p,
                     "trend": key, "trend_label": TREND_LABELS[key], "volatility_pct": vol,
                     "seasonal": si["seasonal"], "seasonal_strength": si["strength"]})
    if len(rows) >= 3:
        lo, hi = np.percentile([r["volatility_pct"] for r in rows], [33, 66])
    else:
        lo, hi = 0.7, 2.0
    for r in rows:
        r["volatility"] = "High" if r["volatility_pct"] > hi else "Low" if r["volatility_pct"] < lo else "Medium"
    return rows


def period_tables(s):
    def tab(rule, fmt, last=None):
        r = s.resample(rule).agg(["mean", "min", "max"]).dropna()
        r["change_pct"] = r["mean"].pct_change() * 100
        r = r.iloc[-last:] if last else r
        return [{"period": fmt(i), "avg_price": float(x["mean"]), "min": float(x["min"]), "max": float(x["max"]),
                 "change_pct": None if pd.isna(x["change_pct"]) else float(x["change_pct"])} for i, x in r.iterrows()]
    return {"weekly": tab("W-MON", lambda d: d.strftime("%d %b %Y"), 26),
            "monthly": tab("MS", lambda d: d.strftime("%b %Y"), 24),
            "quarterly": tab("QS", lambda d: f"{d.year} Q{(d.month - 1) // 3 + 1}"),
            "yearly": tab("YS", lambda d: str(d.year))}


def trends(df, product_id=None):
    rows = product_trends(df)
    out = {"products": rows, "selected": None}
    pid = int(product_id) if product_id else (rows[0]["product_id"] if rows else None)
    if pid:
        g = df[df.product_id == pid]
        s = daily(g, "historical_price")
        r = next((x for x in rows if x["product_id"] == pid), None)
        if r:
            out["selected"] = {**r, "periods": period_tables(s), "explanation": explain(g, s, r["trend"]),
                               "seasonal_info": seasonal_info(s),
                               "note": "Edge periods may be partial. Period averages use daily market (historical) price."}
    out["counts"] = {k: sum(1 for r in rows if r["trend"] == k) for k in TREND_LABELS}
    out["volatility_counts"] = {k: sum(1 for r in rows if r["volatility"] == k) for k in ("High", "Medium", "Low")}
    return out


# ------------------------------------------------------------------ dashboard
def dashboard(df):
    d = with_money(df)
    rows = product_trends(df)
    cat_idx = d.assign(m=d.date.dt.strftime("%Y-%m"))
    cat_idx["idx"] = cat_idx.historical_price / cat_idx.groupby("product_id").historical_price.transform("first") * 100
    price_trend = cat_idx.groupby(["m", "category"]).idx.mean().unstack()
    months = list(price_trend.index)
    monthly = d.assign(m=d.date.dt.strftime("%Y-%m")).groupby("m").agg(
        revenue=("revenue", "sum"), profit=("profit", "sum"), demand=("demand_qty", "sum"), supply=("supply_qty", "sum"))
    overall_idx = cat_idx.groupby("m").idx.mean()
    pred_final, last_now = [], []
    for pid, g in df.groupby("product_id"):
        try:
            s = daily(g, "historical_price")
            fc = predictor.quick_forecast(s, 30)
            pred_final.append(fc.mean())
            last_now.append(s.iloc[-30:].mean())
        except Exception:
            pass
    rev_fc = prof_fc = None
    try:
        rev_fc = float(predictor.quick_forecast(daily(d, "revenue", "sum"), 30).sum())
        prof_fc = float(predictor.quick_forecast(daily(d, "profit", "sum"), 30).sum())
    except Exception:
        pass
    n_inc = sum(r["trend"] == "increasing" for r in rows)
    n_dec = sum(r["trend"] == "decreasing" for r in rows)
    status = "Bullish" if n_inc > n_dec * 1.5 and n_inc > len(rows) * 0.3 else \
        "Bearish" if n_dec > n_inc * 1.5 and n_dec > len(rows) * 0.3 else "Mixed / Stable"
    last30 = d[d.date > d.date.max() - pd.Timedelta(days=30)]
    pm = float(np.mean(pred_final) / np.mean(last_now) * 100 - 100) if pred_final else None
    return {
        "kpis": {"total_products": int(df.product_id.nunique()), "categories": int(df.category.nunique()),
                 "total_sales_units": float(d.sales_qty.sum()), "total_revenue": float(d.revenue.sum()),
                 "avg_market_price": float(df.historical_price.mean()),
                 "predicted_price_change_pct": pm, "avg_demand": float(df.demand_qty.mean()),
                 "expected_revenue_30d": rev_fc, "potential_profit_30d": prof_fc,
                 "recent_revenue_30d": float(last30.revenue.sum()), "recent_profit_30d": float(last30.profit.sum()),
                 "trend_status": status, "bullish": n_inc, "bearish": n_dec,
                 "stable": len(rows) - n_inc - n_dec, "date_min": df.date.min(), "date_max": df.date.max()},
        "price_trend": {"labels": months, "series": {c: price_trend[c].round(2).tolist() for c in price_trend.columns}},
        "sales": {"labels": list(monthly.index), "revenue": monthly.revenue.round(0).tolist(), "profit": monthly.profit.round(0).tolist()},
        "demand_supply": {"labels": list(monthly.index), "demand": monthly.demand.tolist(), "supply": monthly.supply.tolist()},
        "category_price": d.groupby("category").historical_price.mean().round(2).to_dict(),
        "category_revenue": d.groupby("category").revenue.sum().round(0).to_dict(),
        "monthly_trend": {"labels": months, "index": overall_idx.round(2).tolist(),
                          "mom_pct": (overall_idx.pct_change() * 100).round(2).tolist()},
        "top_increasing": sorted([r for r in rows if r["change_30d"] > 0], key=lambda r: -r["change_30d"])[:5],
        "top_decreasing": sorted([r for r in rows if r["change_30d"] < 0], key=lambda r: r["change_30d"])[:5],
    }


# ------------------------------------------------------------------ EDA
def eda(df, product_id=None, category=None):
    g = scope(df, product_id, category)
    if g.empty:
        raise ValueError("No data for the selected filter.")
    multi = g.product_id.nunique() > 1
    rel = g[NUM_COLS] / g.groupby("product_id")[NUM_COLS].transform("mean")
    desc = []
    for c in NUM_COLS:
        x = g[c]
        mode = x.round(2).mode()
        desc.append({"column": c, "count": int(x.count()), "mean": x.mean(), "median": x.median(),
                     "mode": mode.iloc[0] if len(mode) else None, "std": x.std(), "min": x.min(), "max": x.max(),
                     "q1": x.quantile(.25), "q3": x.quantile(.75), "skew": x.skew()})
    base = (rel.historical_price * 100) if multi else g.historical_price
    counts, edges = np.histogram(base, bins=20)
    hist = {"labels": [f"{edges[i]:.1f}–{edges[i + 1]:.1f}" for i in range(20)], "counts": counts.tolist(),
            "unit": "price index (100 = product average)" if multi else "price"}
    corr = (rel if multi else g[NUM_COLS]).corr()
    gm = g.assign(month=g.date.dt.month, pidx=rel.historical_price * 100)
    mon = gm.groupby("month").agg(price_index=("pidx", "mean"), demand=("demand_qty", "mean"), supply=("supply_qty", "mean"))
    seas = gm.groupby("season").agg(price_index=("pidx", "mean"), demand=("demand_qty", "mean"), supply=("supply_qty", "mean"))
    outliers, extreme = [], []
    for c in ("historical_price", "demand_qty", "supply_qty", "sales_qty", "competitor_price"):
        grp = g.groupby("product_id")[c]
        q1, q3 = grp.transform(lambda s: s.quantile(.25)), grp.transform(lambda s: s.quantile(.75))
        iqr = q3 - q1
        mask = (g[c] < q1 - 1.5 * iqr) | (g[c] > q3 + 1.5 * iqr)
        outliers.append({"column": c, "count": int(mask.sum()), "pct": float(mask.mean() * 100)})
        if c == "historical_price":
            extreme = g[mask].assign(deviation_pct=((g[c] - grp.transform("median")) / grp.transform("median") * 100).abs()) \
                .sort_values("deviation_pct", ascending=False).head(10)[["product_name", "date", "historical_price", "deviation_pct"]]
    cat = []
    for c, x in g.groupby("category"):
        vols = [daily(p, "historical_price").pct_change().std() * 100 for _, p in x.groupby("product_id")]
        cat.append({"category": c, "products": int(x.product_id.nunique()), "avg_price": x.historical_price.mean(),
                    "avg_volatility_pct": float(np.nanmean(vols)), "avg_demand": x.demand_qty.mean(),
                    "avg_supply": x.supply_qty.mean(), "units_sold": x.sales_qty.sum()})
    return {"scope": {"rows": len(g), "products": int(g.product_id.nunique()), "multi_product": multi,
                      "note": "Multi-product views use values relative to each product's own average so different price scales are comparable." if multi else None},
            "descriptive": desc, "histogram": hist,
            "correlation": {"labels": list(corr.columns), "matrix": corr.round(2).values.tolist()},
            "monthly": {"labels": [calendar.month_abbr[m] for m in mon.index], **mon.round(2).to_dict("list")},
            "seasonal": {"labels": list(seas.index), **seas.round(2).to_dict("list")},
            "outliers": outliers, "extreme_outliers": extreme, "categories": cat}


def clusters(df, k=3):
    rows = []
    for pid, g in df.groupby("product_id"):
        s = daily(g, "historical_price")
        rows.append({"product_id": int(pid), "product_name": g.product_name.iloc[0], "category": g.category.iloc[0],
                     "avg_price": float(s.mean()), "volatility_pct": float(s.pct_change().std() * 100),
                     "margin_pct": float((g.selling_price - g.cost_price).sum() / g.selling_price.sum() * 100),
                     "price_growth_pct": growth(s, min(90, max(len(s) // 4, 7))), "avg_demand": float(g.demand_qty.mean())})
    f = pd.DataFrame(rows)
    if len(f) < 3:
        raise ValueError("Clustering needs at least 3 products.")
    k = min(k, len(f) - 1)
    X = np.column_stack([np.log(f.avg_price), f.volatility_pct, f.margin_pct, f.price_growth_pct, np.log(f.avg_demand + 1)])
    Z = StandardScaler().fit_transform(X)
    km = KMeans(n_clusters=k, n_init=10, random_state=42).fit(Z)
    f["cluster"] = km.labels_
    names = ["price level", "volatility", "margin", "price growth", "demand volume"]
    summ = []
    for c in range(k):
        cen, members = km.cluster_centers_[c], f[f.cluster == c]
        order = np.argsort(-np.abs(cen))[:2]
        traits = [("High " if cen[i] > 0 else "Low ") + names[i] for i in order]
        summ.append({"cluster": c, "label": f"Cluster {c + 1}: " + ", ".join(traits), "size": len(members),
                     "avg_price": members.avg_price.mean(), "volatility_pct": members.volatility_pct.mean(),
                     "margin_pct": members.margin_pct.mean(), "members": members.product_name.tolist()})
    sil = float(silhouette_score(Z, km.labels_)) if len(f) > k else None
    return {"products": f, "clusters": summ, "silhouette": sil, "features": names}


# ------------------------------------------------------------------ demand & supply
SITUATIONS = {(True, False): "High Demand + Low Supply: Possible Price Increase",
              (False, True): "Low Demand + High Supply: Possible Price Decrease",
              (True, True): "High Demand + High Supply: Balanced / Competitive Market",
              (False, False): "Low Demand + Low Supply: Low Market Activity"}


def demand_supply(df, product_id=None, category=None):
    g = scope(df, product_id, category)
    if g.empty:
        raise ValueError("No data for the selected filter.")
    rows = []
    for pid, p in g.groupby("product_id"):
        dem, sup, sal, inv = daily(p, "demand_qty"), daily(p, "supply_qty"), daily(p, "sales_qty"), daily(p, "inventory")
        d_idx, s_idx = dem.iloc[-30:].mean() / dem.median(), sup.iloc[-30:].mean() / sup.median()
        gap = float(dem.iloc[-30:].mean() - sup.iloc[-30:].mean())
        gap_pct = gap / sup.iloc[-30:].mean() * 100
        cover = float(inv.iloc[-7:].mean() / max(sal.iloc[-30:].mean(), 1e-9))
        status = "Shortage risk" if (gap_pct > 10 or cover < 7) else "Excess inventory" if cover > 45 else "Adequate"
        rows.append({"product_id": int(pid), "product_name": p.product_name.iloc[0], "category": p.category.iloc[0],
                     "avg_demand_30d": float(dem.iloc[-30:].mean()), "avg_supply_30d": float(sup.iloc[-30:].mean()),
                     "gap": gap, "gap_pct": float(gap_pct), "demand_growth_pct": growth(dem), "supply_growth_pct": growth(sup),
                     "demand_index": float(d_idx), "supply_index": float(s_idx), "inventory_cover_days": cover,
                     "situation": SITUATIONS[(bool(d_idx >= 1), bool(s_idx >= 1))], "status": status})
    dd, ss = daily(g, "demand_qty", "sum"), daily(g, "supply_qty", "sum")
    mon = g.assign(m=g.date.dt.strftime("%Y-%m")).groupby("m").agg(demand=("demand_qty", "mean"), supply=("supply_qty", "mean"))
    fc = None
    try:
        r = predictor.quick_forecast(dd, 30)
        fc = {"history_labels": [d for d in dd.index[-60:]], "history": dd.iloc[-60:].tolist(),
              "labels": list(pd.date_range(dd.index[-1] + pd.Timedelta(days=1), periods=30)), "forecast": r.tolist(),
              "mean_forecast": float(r.mean()), "recent_mean": float(dd.iloc[-30:].mean())}
    except Exception:
        pass
    counts = {}
    for r in rows:
        counts[r["situation"]] = counts.get(r["situation"], 0) + 1
    return {"products": rows, "situation_counts": counts,
            "status_counts": {k: sum(1 for r in rows if r["status"] == k) for k in ("Shortage risk", "Excess inventory", "Adequate")},
            "monthly": {"labels": list(mon.index), "demand": mon.demand.round(1).tolist(), "supply": mon.supply.round(1).tolist()},
            "demand_forecast": fc,
            "rules": "Index = last-30-day average divided by the product's own historical median. 'High' means index ≥ 1."}


# ------------------------------------------------------------------ competitors
def competitors(df, product_id=None, category=None, window=30):
    g = scope(df, None, category)
    rows = []
    for pid, p in g.groupby("product_id"):
        w = p[p.date > p.date.max() - pd.Timedelta(days=window)]
        our, comp = w.selling_price.mean(), w.competitor_price.mean()
        pct = (our - comp) / comp * 100
        pos = "Below Market Price" if pct < -3 else "Above Market Price" if pct > 3 else "Competitive Price"
        rows.append({"product_id": int(pid), "product_name": p.product_name.iloc[0], "category": p.category.iloc[0],
                     "our_price": float(our), "avg_competitor": float(comp), "lowest_competitor": float(w.competitor_price.min()),
                     "highest_competitor": float(w.competitor_price.max()), "difference": float(our - comp),
                     "difference_pct": float(pct), "position": pos})
    sel = None
    pid = int(product_id) if product_id else (rows[0]["product_id"] if rows else None)
    if pid:
        p = df[df.product_id == pid].tail(120)
        sel = {"product_id": pid, "product_name": p.product_name.iloc[0], "labels": list(p.date),
               "our": p.selling_price.round(2).tolist(), "competitor": p.competitor_price.round(2).tolist(),
               "market": p.historical_price.round(2).tolist()}
    return {"products": rows, "selected": sel, "window_days": window,
            "position_counts": {k: sum(1 for r in rows if r["position"] == k)
                                for k in ("Below Market Price", "Competitive Price", "Above Market Price")},
            "rules": "Compared over the last 30 days. Within ±3% of the average competitor price = Competitive."}


# ------------------------------------------------------------------ profit
def profit(df, product_id=None, category=None):
    g = with_money(scope(df, product_id, category))
    if g.empty:
        raise ValueError("No data for the selected filter.")
    tot = {"revenue": float(g.revenue.sum()), "cost": float(g.total_cost.sum()), "profit": float(g.profit.sum()),
           "units": float(g.sales_qty.sum())}
    tot["margin_pct"] = _margin(tot["profit"], tot["revenue"])
    dly = g.groupby("date").agg(revenue=("revenue", "sum"), profit=("profit", "sum")).tail(90)
    mon = g.assign(m=g.date.dt.strftime("%Y-%m")).groupby("m").agg(revenue=("revenue", "sum"), cost=("total_cost", "sum"), profit=("profit", "sum"))
    mon["margin_pct"] = mon.profit / mon.revenue * 100
    yr = g.assign(y=g.date.dt.year).groupby("y").agg(revenue=("revenue", "sum"), cost=("total_cost", "sum"), profit=("profit", "sum"), days=("date", "nunique"))
    yr["margin_pct"] = yr.profit / yr.revenue * 100
    prod = g.groupby("product_name").agg(category=("category", "first"), revenue=("revenue", "sum"), cost=("total_cost", "sum"),
                                         profit=("profit", "sum"), units=("sales_qty", "sum"))
    prod["margin_pct"] = prod.profit / prod.revenue * 100
    cat = g.groupby("category").agg(revenue=("revenue", "sum"), cost=("total_cost", "sum"), profit=("profit", "sum"), units=("sales_qty", "sum"))
    cat["margin_pct"] = cat.profit / cat.revenue * 100
    fc = None
    try:
        rs, ps = daily(g, "revenue", "sum"), daily(g, "profit", "sum")
        r, p = predictor.quick_forecast(rs, 30), predictor.quick_forecast(ps, 30)
        fc = {"history_labels": list(rs.index[-60:]), "revenue_history": rs.iloc[-60:].round(0).tolist(),
              "profit_history": ps.iloc[-60:].round(0).tolist(),
              "labels": list(pd.date_range(rs.index[-1] + pd.Timedelta(days=1), periods=30)),
              "revenue": r.round(0).tolist(), "profit": p.round(0).tolist(),
              "revenue_total_30d": float(r.sum()), "profit_total_30d": float(p.sum()),
              "recent_revenue_30d": float(rs.iloc[-30:].sum()), "recent_profit_30d": float(ps.iloc[-30:].sum())}
    except Exception:
        pass
    return {"totals": tot,
            "daily": {"labels": list(dly.index), "revenue": dly.revenue.round(0).tolist(), "profit": dly.profit.round(0).tolist()},
            "monthly": mon.reset_index(), "annual": yr.reset_index().rename(columns={"y": "year"}),
            "products": prod.reset_index().sort_values("profit", ascending=False),
            "categories": cat.reset_index().sort_values("profit", ascending=False), "forecast": fc,
            "formulas": "Revenue = Selling Price × Sales Quantity; Total Cost = Cost Price × Sales Quantity; Profit = Revenue − Total Cost; Margin = Profit ÷ Revenue × 100."}


# ------------------------------------------------------------------ notifications & search
def notifications(df):
    out = []
    ds = demand_supply(df)
    sh = [r["product_name"] for r in ds["products"] if r["status"] == "Shortage risk"]
    ex = [r["product_name"] for r in ds["products"] if r["status"] == "Excess inventory"]
    if sh:
        out.append({"level": "warning", "text": f"Shortage risk: {', '.join(sh[:4])}" + (" and more" if len(sh) > 4 else "")})
    if ex:
        out.append({"level": "info", "text": f"Excess inventory: {', '.join(ex[:4])}" + (" and more" if len(ex) > 4 else "")})
    tr = product_trends(df)
    dec = sorted([r for r in tr if r["trend"] == "decreasing"], key=lambda r: r["change_30d"])[:3]
    inc = sorted([r for r in tr if r["trend"] == "increasing"], key=lambda r: -r["change_30d"])[:3]
    for r in dec:
        out.append({"level": "danger", "text": f"{r['product_name']} is in a bearish trend ({r['change_30d']:+.1f}% in 30 days)"})
    for r in inc:
        out.append({"level": "success", "text": f"{r['product_name']} is in a bullish trend ({r['change_30d']:+.1f}% in 30 days)"})
    above = [r["product_name"] for r in competitors(df)["products"] if r["position"] == "Above Market Price"]
    if above:
        out.append({"level": "warning", "text": f"Priced above competitors: {', '.join(above[:4])}"})
    return out[:10]
