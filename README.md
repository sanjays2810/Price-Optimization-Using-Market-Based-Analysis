# Price Optimization and Future Market Trend Analysis System

Academic Data Mining / Machine Learning project. FastAPI + MySQL + Pandas/scikit-learn/statsmodels + Bootstrap 5 + Chart.js.
Works fully offline: no external market API. (Bootstrap/Chart.js load from a CDN; see "Offline use" below.)

## Quick start (Windows CMD)

```cmd
cd C:\Projects\price_optimization_system
setup.bat
```
1. Make sure **MySQL Server is running** (Services -> MySQL80, or MySQL Workbench shows a connected server).
2. Open `.env` and set `DB_PASSWORD=` to your MySQL password.
3. Check everything: `venv\Scripts\activate` then `python check_env.py`
4. Start: `run.bat` then open **http://127.0.0.1:8000**

The first start creates the database `price_optimization_db`, all 10 tables, a demo user, and loads the
**simulated** sample dataset (about 17,500 rows, takes a few seconds). Optional: `pip install xgboost` enables the XGBoost model.

No MySQL yet? For a quick trial put `DATABASE_URL=sqlite:///./local_test.db` in `.env`. Use MySQL for the final project.

## Project structure
```
app/
  main.py            FastAPI app, startup (creates DB, seeds sample data), error handlers
  config.py          settings read from .env
  database.py        SQLAlchemy engine/session, auto-creates MySQL database
  models/tables.py   10 tables: users, categories, products, uploaded_datasets, market_data,
                     competitor_prices, sales_records, prediction_results, optimization_results, analysis_reports
  schemas/schemas.py Pydantic request validation
  routers/api.py     all REST endpoints (/docs shows them)
  services/
    sample_data.py   synthetic data generator (clearly labelled SIMULATED)
    data_service.py  read -> validate -> clean -> save to MySQL -> load
    analytics.py     dashboard, EDA, K-Means, trends, demand/supply, competitors, profit
    optimizer.py     price optimization engine
    reports.py       PDF (reportlab) and Excel (openpyxl) reports
  ml/predictor.py    forecasting models + chronological evaluation
frontend/            index.html, static/css, static/js (single-page dashboard)
sql/schema.sql       MySQL schema (optional manual setup)
tests/test_smoke.py  automated end-to-end test
data/                uploads, sample files, generated reports
```

## Data mining workflow (where each step lives)
Raw data -> `data_service.read_file` | Preprocessing/cleaning -> `clean_dataset` | EDA -> `analytics.eda` |
Feature engineering -> `predictor._lin_features`, `_tree_row` (lags, returns, deviations, seasonality) |
Training/evaluation -> `predictor.run_forecast` (chronological 80/20 split) | Prediction -> `/api/predict` |
Trend analysis -> `analytics.trends` | Optimization -> `optimizer.optimize` | Visualization/reports -> frontend + `reports.py`

## How to test each feature
| Feature | Steps | Expected |
|---|---|---|
| Dashboard | open `/` | 8 KPI cards, 6 charts, top increasing/decreasing tables (all computed from DB) |
| Upload | Dataset Management -> download sample CSV -> upload it | validation report (missing values, duplicates), raw+cleaned preview, "Save" stores to MySQL |
| Bad file | upload any CSV without Product Name/Date/Historical Price | clear error naming missing columns |
| Cleaning | upload sample file | "12 duplicates removed", missing Competitor Price/Inventory filled |
| EDA | Data Analysis | statistics, histogram, correlation heatmap, seasonality, outliers, K-Means segments |
| Prediction | Price Prediction -> product, algorithm, 30 days | forecast with uncertainty band, MAE/MSE/RMSE/R2, backtest line |
| Compare models | "Compare all algorithms" | table ranked by RMSE |
| Trends | Market Trends | bullish/bearish/stable, volatility, weekly/monthly/quarterly/yearly tables, explanation |
| Demand/Supply | Demand & Supply | four market situations, shortage/excess, 30-day demand forecast |
| Optimization | Price Optimization -> Recommend | best/min/max price, expected profit, profit curve, strategy; try cost > price or negative values |
| Competitors | Competitor Analysis | below/competitive/above classification |
| Profit | Profit Analysis | daily/monthly/annual, product & category wise, forecast |
| Reports | Reports -> any type -> PDF/Excel | file downloads and appears in history |
| Automated | `python -m pytest tests -q` | 1 passed |

## Honest methodology notes (good to state in your viva)
* Predictions are estimates, not guaranteed prices. Evaluation uses a **chronological** split, never shuffled.
* Linear Regression uses trend + annual harmonics + weekday terms. Random Forest / Decision Tree / XGBoost predict the next-day
  **log-return** from lagged returns, deviation from moving averages and seasonality, then forecast recursively.
* Moving Average is a flat forecast (baseline). Exponential Smoothing (Holt, damped) and ARIMA(2,1,2) come from statsmodels
  and provide their own intervals; for other models the band is approximate (test RMSE widened with horizon).
* On strongly seasonal data the flat/trend-only baselines can score a negative R2; that is expected and is reported as is.
* Price optimization: a demand-response model `log(sales/demand) = a + e*log(our price/competitor price)` is fitted per product.
  If it is statistically valid (e < -0.2, p < 0.05, R2 >= 0.05) the profit-maximizing price within safe bounds is recommended
  (model-optimal only, and the search is limited to the price range seen in history). Otherwise a weighted heuristic
  (cost 20%, competitor 35%, demand 25%, trend 20%) is used and labelled **not optimal**. Prices never go below cost plus the
  minimum margin unless the loss-making scenario is ticked.
* Sample data is synthetic and labelled as simulated everywhere (dashboard banner, reports).
* Matplotlib/Seaborn are not used because all charts are interactive Chart.js charts.

## Upload format
Required: **Product Name, Date, Historical Price**. Recognised optional columns (names are matched flexibly):
Product ID, Category, Cost Price, Selling Price, Demand Quantity, Supply Quantity, Competitor Price, Sales Quantity,
Inventory, Seasonal Information, Market Location. Missing optional columns are derived with a visible warning.
Each product needs at least 60 daily observations for forecasting.

## Offline use
For a lab with no internet, download these four files into `frontend/static/vendor/` and change the four CDN links in
`frontend/index.html`: bootstrap.min.css, bootstrap-icons.min.css (+ its fonts folder), bootstrap.bundle.min.js, chart.umd.js.

## Troubleshooting
* `Cannot connect to the database` -> start MySQL, fix `DB_PASSWORD` in `.env`.
* `ModuleNotFoundError` -> run `venv\Scripts\activate` first, then `pip install -r requirements.txt`.
* Port busy -> change `--port 8000` in `run.bat`.
* To rebuild the sample data: Dataset Management -> "Load built-in sample dataset".
