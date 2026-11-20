"""Dataset pipeline: read -> validate -> clean -> save to DB -> load for analytics."""
import json
import re
from pathlib import Path

import numpy as np
import pandas as pd
from sqlalchemy import delete, insert, select, update
from sqlalchemy.orm import Session

from app.models import (AnalysisReport, Category, CompetitorPrice, MarketData, OptimizationResult,
                        PredictionResult, Product, SalesRecord, UploadedDataset)
from app.services.sample_data import season_of


class DataError(Exception):
    """Raised for user-fixable dataset problems."""


ALIASES = {
    "product_code": ["product id", "id", "sku", "product code", "item id"],
    "product_name": ["product name", "product", "name", "item", "item name"],
    "category": ["category", "product category", "type", "group"],
    "date": ["date", "datetime", "day", "timestamp", "price date"],
    "historical_price": ["historical price", "price", "market price", "historical market price", "modal price"],
    "cost_price": ["cost price", "cost", "unit cost", "purchase price"],
    "selling_price": ["selling price", "our price", "sale price", "retail price"],
    "demand_qty": ["demand quantity", "demand", "demand qty"],
    "supply_qty": ["supply quantity", "supply", "supply qty", "arrivals"],
    "competitor_price": ["competitor price", "competitor", "rival price"],
    "sales_qty": ["sales quantity", "sales", "quantity sold", "sales qty", "units sold"],
    "inventory": ["inventory", "stock", "stock level", "stock quantity"],
    "season": ["seasonal information", "season", "seasonal"],
    "location": ["market location", "location", "market", "city"],
}
REQUIRED = ["product_name", "date", "historical_price"]
ALL_COLS = list(ALIASES.keys())
NUMERIC = ["historical_price", "cost_price", "selling_price", "demand_qty", "supply_qty",
           "competitor_price", "sales_qty", "inventory"]
PRICE_COLS = ["historical_price", "cost_price", "selling_price", "competitor_price"]
TEXT_COLS = ["product_code", "product_name", "category", "season", "location"]


def _key(s) -> str:
    return re.sub(r"[^a-z0-9]", "", str(s).lower())


LOOKUP = {}
for canon, names in ALIASES.items():
    LOOKUP[_key(canon)] = canon
    for n in names:
        LOOKUP[_key(n)] = canon


def read_file(path: Path) -> pd.DataFrame:
    ext = path.suffix.lower()
    try:
        if ext == ".csv":
            try:
                return pd.read_csv(path)
            except UnicodeDecodeError:
                return pd.read_csv(path, encoding="latin-1")
        return pd.read_excel(path)
    except Exception as exc:
        raise DataError(f"Could not read the file. Check that it is a valid {ext} file. ({exc})")


def standardize(df_raw: pd.DataFrame):
    mapping = {}
    for col in df_raw.columns:
        canon = LOOKUP.get(_key(col))
        if canon and canon not in mapping.values():
            mapping[col] = canon
    df = df_raw[list(mapping.keys())].rename(columns=mapping).copy()
    ignored = [c for c in df_raw.columns if c not in mapping]
    return df, mapping, [str(c) for c in ignored]


def clean_dataset(df_raw: pd.DataFrame):
    """Returns (clean_df, report). Raises DataError when required columns are missing."""
    rep = {"rows_raw": int(len(df_raw)), "warnings": [], "assumptions": []}
    if df_raw.empty:
        raise DataError("The file has no rows.")
    df, mapping, ignored = standardize(df_raw)
    found = list(df.columns)
    missing_req = [c for c in REQUIRED if c not in found]
    if missing_req:
        raise DataError(
            "Missing required column(s): " + ", ".join(missing_req)
            + ". Required: Product Name, Date, Historical Price. Columns found in file: "
            + ", ".join(map(str, df_raw.columns)))
    rep["columns_found"] = found
    rep["columns_missing"] = [c for c in ALL_COLS if c not in found]
    rep["columns_ignored"] = ignored

    for c in TEXT_COLS:
        if c in df:
            s = df[c].astype(str).str.strip()
            s[s.isin(["", "nan", "None", "NaT", "<NA>"])] = np.nan
            df[c] = s
    rep["missing_before"] = {c: int(df[c].isna().sum()) for c in df.columns}

    # dates
    parsed = pd.to_datetime(df["date"], errors="coerce")
    if parsed.isna().mean() > 0.5:
        alt = pd.to_datetime(df["date"], errors="coerce", dayfirst=True)
        if alt.isna().sum() < parsed.isna().sum():
            parsed = alt
    rep["invalid_dates_removed"] = int(parsed.isna().sum())
    df["date"] = parsed.dt.normalize()
    df = df[df["date"].notna()]
    rep["missing_product_name_removed"] = int(df["product_name"].isna().sum())
    df = df[df["product_name"].notna()].copy()

    # numeric coercion
    type_errors = {}
    for c in NUMERIC:
        if c in df:
            had = df[c].notna()
            if not pd.api.types.is_numeric_dtype(df[c]):
                df[c] = pd.to_numeric(df[c].astype(str).str.replace(r"[₹$€£,\s]", "", regex=True), errors="coerce")
            type_errors[c] = int((had & df[c].isna()).sum())
    rep["type_errors_converted_to_missing"] = type_errors
    inv = 0
    for c in NUMERIC:
        if c in df:
            bad = (df[c] <= 0) if c in PRICE_COLS else (df[c] < 0)
            inv += int(bad.sum())
            df.loc[bad, c] = np.nan
    rep["invalid_values_set_missing"] = inv

    # identifiers
    if "category" not in df:
        df["category"] = "Uncategorized"
        rep["warnings"].append("No Category column: all products placed in 'Uncategorized'.")
    df["category"] = df["category"].fillna("Uncategorized")
    if "location" not in df:
        df["location"] = "Not specified"
    df["location"] = df["location"].fillna("Not specified")
    names = df["product_name"].unique()
    auto = {n: f"P{i + 1:03d}" for i, n in enumerate(sorted(names))}
    if "product_code" not in df:
        df["product_code"] = df["product_name"].map(auto)
        rep["warnings"].append("No Product ID column: IDs were generated from product names.")
    df["product_code"] = df["product_code"].fillna(df["product_name"].map(auto))
    first = df.groupby("product_code")[["product_name", "category"]].first()
    df["product_name"] = df["product_code"].map(first["product_name"])
    df["category"] = df["product_code"].map(first["category"])

    # duplicates
    before = len(df)
    df = df.drop_duplicates(subset=["product_code", "date", "location"], keep="first")
    rep["duplicates_removed"] = int(before - len(df))
    df = df.sort_values(["product_code", "date"]).reset_index(drop=True)

    # missing values
    for c in NUMERIC:
        if c in df:
            df[c] = df.groupby("product_code")[c].transform(lambda s: s.interpolate(limit_direction="both"))
            df[c] = df[c].fillna(df[c].median())
    hp = df["historical_price"]
    if "cost_price" not in df:
        df["cost_price"] = (hp * 0.70).round(2)
        rep["assumptions"].append("Cost Price not provided: assumed 70% of Historical Price. Profit figures are illustrative.")
    if "selling_price" not in df:
        df["selling_price"] = hp
        rep["assumptions"].append("Selling Price not provided: assumed equal to Historical Price.")
    if "competitor_price" not in df:
        df["competitor_price"] = hp
        rep["assumptions"].append("Competitor Price not provided: assumed equal to Historical Price. Competitor analysis is not meaningful.")
    if "demand_qty" not in df:
        df["demand_qty"] = (df["sales_qty"] / 0.9) if "sales_qty" in df else 100.0
        rep["assumptions"].append("Demand Quantity not provided: derived from Sales Quantity (or a constant).")
    if "sales_qty" not in df:
        df["sales_qty"] = df["demand_qty"] * 0.9
        rep["assumptions"].append("Sales Quantity not provided: assumed 90% of Demand Quantity.")
    if "supply_qty" not in df:
        df["supply_qty"] = df["demand_qty"]
        rep["assumptions"].append("Supply Quantity not provided: assumed equal to Demand Quantity.")
    if "inventory" not in df:
        df["inventory"] = df["sales_qty"] * 14
        rep["assumptions"].append("Inventory not provided: assumed 14 days of sales.")
    if "season" not in df:
        df["season"] = np.nan
    df["season"] = df["season"].fillna(df["date"].dt.month.map(season_of))

    # outlier report (IQR within each product) - reported, not removed
    outl = {}
    for c in ("historical_price", "demand_qty", "supply_qty", "sales_qty"):
        g = df.groupby("product_code")[c]
        q1, q3 = g.transform(lambda s: s.quantile(.25)), g.transform(lambda s: s.quantile(.75))
        iqr = q3 - q1
        outl[c] = int(((df[c] < q1 - 1.5 * iqr) | (df[c] > q3 + 1.5 * iqr)).sum())
    rep["outliers_flagged"] = outl
    rep["rows_clean"] = int(len(df))
    rep["products"] = int(df["product_code"].nunique())
    rep["categories"] = int(df["category"].nunique())
    rep["date_min"] = df["date"].min().strftime("%Y-%m-%d")
    rep["date_max"] = df["date"].max().strftime("%Y-%m-%d")
    if rep["rows_clean"] < 60:
        rep["warnings"].append("Fewer than 60 rows: prediction modules need at least 60 daily observations per product.")
    per = df.groupby("product_code").size()
    if (per < 60).any():
        rep["warnings"].append(f"{int((per < 60).sum())} product(s) have fewer than 60 observations; they cannot be forecast.")
    if rep["duplicates_removed"]:
        rep["warnings"].append(f"{rep['duplicates_removed']} duplicate record(s) were removed.")
    filled = {c: n for c, n in rep["missing_before"].items() if n and c in NUMERIC}
    if filled:
        rep["warnings"].append("Missing numeric values were filled by per-product interpolation: "
                               + ", ".join(f"{c} ({n})" for c, n in filled.items()) + ".")
    rep["status"] = "Passed with warnings" if (rep["warnings"] or rep["assumptions"]) else "Passed"
    cols = ["product_code", "product_name", "category", "date"] + NUMERIC + ["season", "location"]
    return df[cols], rep


# ---------------------------------------------------------------- database
_CACHE: dict = {}


def invalidate():
    _CACHE.clear()


def _chunks(rows, n=5000):
    for i in range(0, len(rows), n):
        yield rows[i:i + n]


def save_dataset(db: Session, df: pd.DataFrame, name: str, filename: str, source: str, report: dict) -> UploadedDataset:
    db.execute(update(UploadedDataset).values(is_active=False))
    ds = UploadedDataset(name=name, filename=filename, source=source, rows_raw=report["rows_raw"],
                         rows_clean=len(df), date_min=df["date"].min().date(), date_max=df["date"].max().date(),
                         is_active=True, validation_report=json.dumps(report))
    db.add(ds)
    db.flush()
    cats = {c.name: c.id for c in db.scalars(select(Category))}
    for cname in df["category"].unique():
        if cname not in cats:
            c = Category(name=str(cname)[:100])
            db.add(c)
            db.flush()
            cats[cname] = c.id
    prod_rows = df.drop_duplicates("product_code")[["product_code", "product_name", "category"]]
    pid = {}
    for r in prod_rows.itertuples(index=False):
        p = Product(dataset_id=ds.id, category_id=cats[r.category], product_code=str(r.product_code)[:60],
                    name=str(r.product_name)[:150])
        db.add(p)
        db.flush()
        pid[r.product_code] = p.id
    d = df.copy()
    d["product_id"] = d["product_code"].map(pid)
    d["record_date"] = d["date"].dt.date
    d["dataset_id"] = ds.id
    m_cols = ["dataset_id", "product_id", "record_date", "historical_price", "cost_price", "selling_price",
              "demand_qty", "supply_qty", "competitor_price", "sales_qty", "inventory", "season", "location"]
    for ch in _chunks(d[m_cols].to_dict("records")):
        db.execute(insert(MarketData), ch)
    comp = d[["dataset_id", "product_id", "record_date", "location", "competitor_price"]]
    for ch in _chunks(comp.to_dict("records")):
        db.execute(insert(CompetitorPrice), ch)
    s = d[["dataset_id", "product_id", "record_date", "sales_qty"]].copy()
    s["revenue"] = d["selling_price"] * d["sales_qty"]
    s["total_cost"] = d["cost_price"] * d["sales_qty"]
    s["profit"] = s["revenue"] - s["total_cost"]
    for ch in _chunks(s.to_dict("records")):
        db.execute(insert(SalesRecord), ch)
    db.commit()
    invalidate()
    return ds


def delete_dataset(db: Session, dataset_id: int):
    for model in (SalesRecord, CompetitorPrice, MarketData, PredictionResult, OptimizationResult, Product):
        db.execute(delete(model).where(model.dataset_id == dataset_id))
    db.execute(delete(UploadedDataset).where(UploadedDataset.id == dataset_id))
    db.commit()
    if not db.scalar(select(UploadedDataset).where(UploadedDataset.is_active == True)):  # noqa: E712
        last = db.scalar(select(UploadedDataset).order_by(UploadedDataset.id.desc()))
        if last:
            last.is_active = True
            db.commit()
    invalidate()


def activate_dataset(db: Session, dataset_id: int):
    if not db.get(UploadedDataset, dataset_id):
        raise DataError("Dataset not found.")
    db.execute(update(UploadedDataset).values(is_active=False))
    db.execute(update(UploadedDataset).where(UploadedDataset.id == dataset_id).values(is_active=True))
    db.commit()


def active_dataset(db: Session):
    return db.scalar(select(UploadedDataset).where(UploadedDataset.is_active == True))  # noqa: E712


def load_df(db: Session, dataset_id: int) -> pd.DataFrame:
    if dataset_id in _CACHE:
        return _CACHE[dataset_id]
    stmt = (select(MarketData.product_id, Product.product_code, Product.name.label("product_name"),
                   Category.name.label("category"), MarketData.record_date.label("date"),
                   MarketData.historical_price, MarketData.cost_price, MarketData.selling_price,
                   MarketData.demand_qty, MarketData.supply_qty, MarketData.competitor_price,
                   MarketData.sales_qty, MarketData.inventory, MarketData.season, MarketData.location)
            .join(Product, Product.id == MarketData.product_id)
            .join(Category, Category.id == Product.category_id)
            .where(MarketData.dataset_id == dataset_id)
            .order_by(MarketData.product_id, MarketData.record_date))
    df = pd.read_sql(stmt, db.connection())
    df["date"] = pd.to_datetime(df["date"])
    _CACHE[dataset_id] = df
    return df


def load_sample(db: Session):
    from app.services.sample_data import write_sample_files
    old = db.scalars(select(UploadedDataset).where(UploadedDataset.source == "sample")).all()
    for o in old:
        delete_dataset(db, o.id)
    files = write_sample_files()
    df, rep = clean_dataset(files["df"])
    rep["note"] = "SIMULATED sample data generated by this application. Not real market observations."
    return save_dataset(db, df, "Sample Dataset (Simulated)", "sample_market_data.csv", "sample", rep)
