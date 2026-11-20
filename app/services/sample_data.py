"""Synthetic (SIMULATED) market data generator. Not real market observations."""
from datetime import date, timedelta

import numpy as np
import pandas as pd

from app.config import SAMPLE_DIR

# code, name, category, base price, annual trend, season amp, peak month, noise,
# price elasticity (vs competitor), base market demand, cost ratio, location
PRODUCTS = [
    ("VEG-001", "Tomato", "Vegetables", 30, 0.04, 0.30, 12, 0.018, -3.5, 900, 0.70, "Erode"),
    ("VEG-002", "Onion", "Vegetables", 28, 0.05, 0.22, 10, 0.014, -3.2, 1200, 0.72, "Salem"),
    ("VEG-003", "Potato", "Vegetables", 25, 0.03, 0.10, 8, 0.008, -3.0, 1500, 0.74, "Coimbatore"),
    ("VEG-004", "Carrot", "Vegetables", 40, -0.02, 0.18, 1, 0.012, -3.6, 600, 0.70, "Madurai"),
    ("FRU-001", "Banana", "Fruits", 45, 0.03, 0.08, 4, 0.007, -3.0, 1000, 0.72, "Erode"),
    ("FRU-002", "Apple", "Fruits", 150, 0.06, 0.12, 11, 0.009, -3.4, 500, 0.74, "Bengaluru"),
    ("FRU-003", "Mango", "Fruits", 90, 0.00, 0.40, 5, 0.014, -4.0, 400, 0.68, "Salem"),
    ("FRU-004", "Grapes", "Fruits", 80, 0.02, 0.20, 3, 0.011, -3.8, 450, 0.70, "Coimbatore"),
    ("ELE-001", "Smartphone", "Electronics", 18000, -0.08, 0.04, 11, 0.004, -4.2, 60, 0.80, "Chennai"),
    ("ELE-002", "Wireless Earbuds", "Electronics", 2500, -0.10, 0.05, 10, 0.006, -4.5, 140, 0.68, "Bengaluru"),
    ("ELE-003", "Smart TV", "Electronics", 32000, -0.07, 0.06, 10, 0.005, -4.0, 35, 0.82, "Chennai"),
    ("ELE-004", "Power Bank", "Electronics", 1500, -0.04, 0.03, 12, 0.005, -4.8, 180, 0.66, "Madurai"),
    ("GRO-001", "Basmati Rice", "Grocery Products", 95, 0.05, 0.05, 11, 0.004, -3.1, 800, 0.76, "Chennai"),
    ("GRO-002", "Cooking Oil", "Grocery Products", 140, 0.04, 0.06, 1, 0.006, -3.4, 700, 0.78, "Coimbatore"),
    ("GRO-003", "Sugar", "Grocery Products", 44, 0.03, 0.07, 6, 0.005, -3.3, 900, 0.80, "Salem"),
    ("GRO-004", "Toor Dal", "Grocery Products", 125, 0.07, 0.09, 2, 0.007, -3.2, 650, 0.75, "Madurai"),
    ("AGR-001", "Wheat", "Agricultural Products", 28, 0.04, 0.12, 4, 0.006, -3.0, 2000, 0.78, "Erode"),
    ("AGR-002", "Paddy", "Agricultural Products", 22, 0.03, 0.15, 2, 0.007, -3.0, 2200, 0.80, "Thanjavur"),
    ("AGR-003", "Cotton", "Agricultural Products", 70, -0.02, 0.18, 12, 0.010, -3.5, 800, 0.74, "Coimbatore"),
    ("AGR-004", "Turmeric", "Agricultural Products", 120, 0.06, 0.25, 3, 0.012, -3.8, 350, 0.70, "Erode"),
    ("FAS-001", "Cotton T-Shirt", "Fashion Products", 450, 0.02, 0.15, 10, 0.005, -4.0, 300, 0.60, "Tiruppur"),
    ("FAS-002", "Denim Jeans", "Fashion Products", 1400, 0.01, 0.12, 11, 0.005, -4.2, 160, 0.62, "Chennai"),
    ("FAS-003", "Silk Saree", "Fashion Products", 2200, 0.03, 0.30, 10, 0.007, -3.6, 70, 0.66, "Kanchipuram"),
    ("FAS-004", "Sneakers", "Fashion Products", 2600, -0.01, 0.10, 12, 0.006, -4.4, 110, 0.64, "Bengaluru"),
]


def season_of(month: int) -> str:
    if month in (12, 1, 2):
        return "Winter"
    if month in (3, 4, 5):
        return "Summer"
    if month in (6, 7, 8, 9):
        return "Monsoon"
    return "Post-Monsoon"


def generate(days: int = 730, seed: int = 42, end_date: date | None = None) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    end = end_date or (date.today() - timedelta(days=1))
    dates = pd.date_range(end=end, periods=days)
    doy = dates.dayofyear.values
    t = np.arange(days)
    weekend = (dates.dayofweek.values >= 5).astype(float)
    frames = []
    for code, name, cat, base, trend, amp, peak, vol, elas, bdem, cratio, loc in PRODUCTS:
        peak_doy = (peak - 1) * 30.4 + 15
        season = np.cos(2 * np.pi * (doy - peak_doy) / 365.25)
        eps = rng.normal(0, vol, days)
        ar = np.zeros(days)
        for i in range(1, days):
            ar[i] = 0.92 * ar[i - 1] + eps[i]
        trend_base = base * (1 + trend * t / 365.25)
        market = trend_base * (1 + amp * season) * np.exp(ar)
        prem = np.repeat(rng.uniform(-0.07, 0.10, size=int(np.ceil(days / 10))), 10)[:days]
        sell = market * (1 + prem)
        comp = market * (1 + rng.normal(0.01, 0.025, days))
        cost = base * cratio * (1 + 0.5 * (market / base - 1))
        demand = bdem * (1 + 0.22 * np.cos(2 * np.pi * (doy - peak_doy - 20) / 365.25)) \
            * (1 + 0.10 * weekend) * (1 + amp * season) ** -0.5 * np.exp(rng.normal(0, 0.07, days))
        supply = bdem * 1.05 * (1 - 0.7 * amp * season) * np.exp(rng.normal(0, 0.06, days))
        sales = 0.55 * demand * (sell / comp) ** elas * np.exp(rng.normal(0, 0.10, days))
        sales = np.maximum(np.round(sales), 0)
        cap = 45 * 0.55 * bdem
        inv = np.zeros(days)
        cur = 12 * 0.55 * bdem
        for i in range(days):
            inflow = 0.55 * supply[i] * (1 - 0.35 * (cur / cap - 0.3))
            cur = float(np.clip(cur + inflow - sales[i], 0, cap))
            inv[i] = cur
        frames.append(pd.DataFrame({
            "Product ID": code, "Product Name": name, "Category": cat, "Date": dates,
            "Historical Price": market.round(2), "Cost Price": cost.round(2),
            "Selling Price": sell.round(2), "Demand Quantity": demand.round().astype(int),
            "Supply Quantity": supply.round().astype(int), "Competitor Price": comp.round(2),
            "Sales Quantity": sales.astype(int), "Inventory": inv.round().astype(int),
            "Seasonal Information": [season_of(m) for m in dates.month], "Market Location": loc,
        }))
    df = pd.concat(frames, ignore_index=True)

    # Inject a few realistic defects so the cleaning pipeline has something to report.
    n = len(df)
    for col in ("Competitor Price", "Inventory"):
        idx = rng.choice(n, size=int(n * 0.002), replace=False)
        df[col] = df[col].astype(float)
        df.loc[idx, col] = np.nan
    dup = df.sample(12, random_state=seed)
    df = pd.concat([df, dup], ignore_index=True).sort_values(["Product ID", "Date"]).reset_index(drop=True)
    return df


def write_sample_files() -> dict:
    df = generate()
    csv_path = SAMPLE_DIR / "sample_market_data.csv"
    xlsx_path = SAMPLE_DIR / "sample_market_data.xlsx"
    df.to_csv(csv_path, index=False)
    df.to_excel(xlsx_path, index=False)
    return {"csv": csv_path, "xlsx": xlsx_path, "df": df}
