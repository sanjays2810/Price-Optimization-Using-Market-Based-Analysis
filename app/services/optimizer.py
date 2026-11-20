"""Price Optimization Engine.

Two modes, always labelled honestly in the output:
  * model-based  - a demand-response (price elasticity) model is fitted from the product's history. If it is
                   statistically valid, the price that maximises expected profit under that model (within safe
                   bounds) is recommended.
  * heuristic    - blend of cost-based, competitor-based, demand-based and trend-based prices. This is a
                   recommendation, NOT claimed to be mathematically optimal.
"""
import numpy as np
import pandas as pd
from scipy import stats

from app.ml import predictor
from app.services.analytics import daily


def estimate_elasticity(g: pd.DataFrame) -> dict:
    d = g[(g.sales_qty > 0) & (g.selling_price > 0) & (g.competitor_price > 0) & (g.demand_qty > 0)]
    res = {"valid": False, "n": int(len(d)), "elasticity": None, "p_value": None, "r_squared": None,
           "reason": None, "model": "log(sales ÷ demand) = a + e · log(our price ÷ competitor price)"}
    if len(d) < 60:
        res["reason"] = "Fewer than 60 usable observations."
        return res
    x = np.log(d.selling_price / d.competitor_price).values
    y = np.log(d.sales_qty / d.demand_qty).values
    if np.std(x) < 0.01:
        res["reason"] = "Our price barely differs from competitor price in the history, so price response cannot be learned."
        return res
    lr = stats.linregress(x, y)
    res.update(x_lo=float(np.percentile(x, 5)), x_hi=float(np.percentile(x, 95)), elasticity=float(lr.slope), p_value=float(lr.pvalue), r_squared=float(lr.rvalue ** 2), intercept=float(lr.intercept))
    if lr.slope < -0.2 and lr.pvalue < 0.05 and lr.rvalue ** 2 >= 0.05:
        res["valid"] = True
    else:
        res["reason"] = "Estimated price response is not statistically reliable (needs a negative slope, p < 0.05, R² ≥ 0.05)."
    return res


def defaults(df: pd.DataFrame, product_id: int) -> dict:
    g = df[df.product_id == int(product_id)]
    if g.empty:
        raise ValueError("Product not found in the active dataset.")
    w = g[g.date > g.date.max() - pd.Timedelta(days=30)]
    d = {"product_id": int(product_id), "product_name": g.product_name.iloc[0], "category": g.category.iloc[0],
         "current_price": w.selling_price.mean(), "cost_price": w.cost_price.mean(),
         "competitor_price": w.competitor_price.mean(), "competitor_min": w.competitor_price.min(),
         "competitor_max": w.competitor_price.max(), "market_price": w.historical_price.mean(),
         "demand_qty": w.demand_qty.mean(), "supply_qty": w.supply_qty.mean(),
         "inventory": w.inventory.iloc[-7:].mean(), "daily_sales": w.sales_qty.mean(),
         "median_demand": g.demand_qty.median(), "median_supply": g.supply_qty.median()}
    d["expected_demand"] = d["demand_qty"]
    d["predicted_price_change_pct"] = 0.0
    try:
        d["expected_demand"] = float(predictor.quick_forecast(daily(g, "demand_qty"), 30).mean())
        fc = predictor.quick_forecast(daily(g, "historical_price"), 30).mean()
        d["predicted_price_change_pct"] = float((fc / daily(g, "historical_price").iloc[-30:].mean() - 1) * 100)
    except Exception:
        pass
    return {k: (round(float(v), 2) if isinstance(v, (float, np.floating)) else v) for k, v in d.items()}


def optimize(df: pd.DataFrame, product_id: int, inputs: dict, allow_loss=False, min_margin_pct=5.0,
             target_margin_pct=25.0, horizon_days=30) -> dict:
    base = defaults(df, product_id)
    g = df[df.product_id == int(product_id)]
    for k in ("current_price", "cost_price", "competitor_price", "demand_qty", "supply_qty", "inventory", "expected_demand"):
        if inputs.get(k) is not None:
            base[k] = float(inputs[k])
    p0, cost, comp = base["current_price"], base["cost_price"], base["competitor_price"]
    mkt, dem, sup = base["market_price"], base["demand_qty"], base["supply_qty"]
    warnings, components = [], []

    min_price = cost * (1 + min_margin_pct / 100)
    ceilings = [comp * 1.10, mkt * 1.15]
    max_price = max(min(ceilings), min_price * 1.02)
    max_ceiling = max_price
    search_min = cost * 0.7 if allow_loss else min_price
    if allow_loss:
        warnings.append("Loss-making scenario enabled: prices below cost are allowed in the search range.")
    if p0 < cost:
        warnings.append("Current selling price is below cost price: every unit currently sells at a loss.")

    # demand baseline at the current price
    scale = base["expected_demand"] / dem if dem else 1.0
    q0 = base["daily_sales"] * scale
    cover = base["inventory"] / max(base["daily_sales"], 1e-9)

    # heuristic components
    cost_based = cost * (1 + target_margin_pct / 100)
    comp_based = comp
    d_idx = dem / base["median_demand"] if base["median_demand"] else 1
    s_idx = sup / base["median_supply"] if base["median_supply"] else 1
    demand_based = mkt * (1 + float(np.clip(0.25 * (d_idx - s_idx), -0.08, 0.08)))
    trend_based = p0 * (1 + float(np.clip(0.5 * base["predicted_price_change_pct"] / 100, -0.05, 0.05)))
    parts = [("Cost-based (cost + target margin)", cost_based, 0.20), ("Competitor-based (average competitor price)", comp_based, 0.35),
             ("Demand-based (market price adjusted for demand/supply)", demand_based, 0.25),
             ("Trend-based (current price adjusted for predicted market move)", trend_based, 0.20)]
    heur = sum(p * w for _, p, w in parts)
    adj = ""
    if cover > 45:
        heur *= 0.97
        adj = "Inventory cover above 45 days: price lowered 3% to move stock."
    elif cover < 7:
        heur *= 1.03
        adj = "Inventory cover below 7 days: price raised 3% to protect remaining stock."
    heur = float(np.clip(heur, search_min if allow_loss else min_price, max_price))
    components = [{"name": n, "price": float(p), "weight": w} for n, p, w in parts]

    # model-based optimisation
    el = estimate_elasticity(g)
    curve, model_price = [], None
    lo = search_min
    grid = np.linspace(lo, max_price, 120)
    if el["valid"]:
        # never trust the model outside the relative-price range seen in the history
        r_lo, r_hi = comp * np.exp(el["x_lo"]), comp * np.exp(el["x_hi"])
        lo2, hi2 = max(lo, r_lo), min(max_price, r_hi)
        if lo2 < hi2:
            if lo2 > lo or hi2 < max_price:
                warnings.append("Model search limited to the price range observed in history (about "
                                f"{r_lo:.2f}–{r_hi:.2f}); outside it the demand response is not trusted.")
            lo, max_price = lo2, hi2
            grid = np.linspace(lo, max_price, 120)
        else:
            el["valid"], el["reason"] = False, "Allowed price range lies outside the price range seen in the history."
    if el["valid"]:
        e = el["elasticity"]
        qty = q0 * (grid / p0) ** e
        prof = (grid - cost) * qty
        model_price = float(grid[int(np.argmax(prof))])
        curve = [{"price": float(p), "daily_profit": float(pr), "daily_revenue": float(p * q), "daily_qty": float(q)}
                 for p, q, pr in zip(grid[::3], qty[::3], prof[::3])]
        if model_price >= max_price * 0.999:
            warnings.append("The model's profit is still rising at the maximum suggested price, so the recommendation is capped by the competitor/market ceiling.")
        if model_price <= lo * 1.001:
            warnings.append("The model's profit is highest at the lowest allowed price; check cost and demand inputs.")
        mode = "model-based"
        best = model_price
        basis = (f"Fitted price elasticity {e:.2f} (p = {el['p_value']:.3g}, R² = {el['r_squared']:.2f}, n = {el['n']}). "
                 "The recommended price maximises expected daily profit under this fitted model, within the safe price range. "
                 "It is optimal for the model only, not a guarantee of real-world results.")
        exp_qty = float(q0 * (best / p0) ** e)
    else:
        mode = "heuristic"
        best = heur
        basis = ("No statistically valid demand-response model could be fitted (" + (el["reason"] or "") + ") "
                 "so this is a rule-based recommendation. It is NOT claimed to be mathematically optimal, and expected sales "
                 "are assumed unchanged from the baseline because price response is unknown.")
        exp_qty = float(q0)
    if not allow_loss:
        best = max(best, min_price)

    signal = ""
    if d_idx >= 1 and s_idx < 1:
        signal = " Market signal: demand is above normal while supply is tight."
    elif d_idx < 1 and s_idx >= 1:
        signal = " Market signal: demand is soft while supply is ample."
    if cover > 45:
        strategy = "Clearance-oriented pricing: high stock cover, prioritise sell-through."
    elif best >= p0 * 1.01 and d_idx >= 1 and s_idx < 1:
        strategy = "Demand-driven increase: strong demand with tight supply supports a higher price."
    elif best > comp * 1.03:
        strategy = "Premium pricing: price above competitors, justified only if demand holds."
    elif best < comp * 0.97:
        strategy = "Competitive / penetration pricing: price below competitors to gain volume."
    elif best < p0 * 0.99:
        strategy = "Competitor-matched price reduction: realign with the market."
    else:
        strategy = "Competitor-matched pricing: stay within ±3% of the market."
    strategy += signal

    cur_unit = p0 - cost
    cur_daily_profit = cur_unit * q0
    exp_unit = best - cost
    rec_daily_profit = exp_unit * exp_qty
    return {
        "product": {"id": int(product_id), "name": base["product_name"], "category": base["category"]},
        "mode": mode, "inputs_used": {k: base[k] for k in ("current_price", "cost_price", "competitor_price", "demand_qty",
                                                          "supply_qty", "inventory", "expected_demand")},
        "current": {"price": p0, "profit_per_unit": cur_unit, "margin_pct": cur_unit / p0 * 100 if p0 else 0,
                    "daily_qty": q0, "daily_revenue": p0 * q0, "daily_profit": cur_daily_profit},
        "recommended": {"best_price": best, "minimum_profitable_price": min_price, "maximum_suggested_price": max_ceiling,
                        "price_difference": best - p0, "price_change_pct": (best - p0) / p0 * 100 if p0 else 0,
                        "profit_per_unit": exp_unit, "margin_pct": exp_unit / best * 100 if best else 0,
                        "daily_qty": exp_qty, "daily_revenue": best * exp_qty, "daily_profit": rec_daily_profit,
                        "expected_revenue": best * exp_qty * horizon_days, "expected_profit": rec_daily_profit * horizon_days,
                        "horizon_days": horizon_days, "profit_change_pct": (rec_daily_profit - cur_daily_profit) / abs(cur_daily_profit) * 100 if cur_daily_profit else None,
                        "strategy": strategy},
        "heuristic_price": heur, "model_price": model_price, "components": components, "inventory_adjustment": adj,
        "inventory_cover_days": cover, "elasticity": el, "curve": curve, "basis": basis, "warnings": warnings,
        "reference": {"competitor_min": base["competitor_min"], "competitor_max": base["competitor_max"], "market_price": mkt,
                      "predicted_price_change_pct": base["predicted_price_change_pct"]},
        "disclaimer": "Recommendations are decision support based on historical data and stated assumptions, not guarantees.",
    }
