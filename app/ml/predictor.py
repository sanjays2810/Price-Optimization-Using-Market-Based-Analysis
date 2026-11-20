"""Time-series price forecasting. All models use a chronological train/test split (no shuffling)."""
import math
import warnings

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.tree import DecisionTreeRegressor

try:
    from xgboost import XGBRegressor
    HAS_XGB = True
except Exception:  # xgboost is optional
    HAS_XGB = False

ALGORITHMS = {
    "linear_regression": "Linear Regression",
    "random_forest": "Random Forest Regression",
    "decision_tree": "Decision Tree Regression",
    "moving_average": "Moving Average (14-day)",
    "exp_smoothing": "Exponential Smoothing (Holt, damped)",
    "arima": "ARIMA(2,1,2)",
}
if HAS_XGB:
    ALGORITHMS["xgboost"] = "XGBoost Regression"

MIN_POINTS = 60
DISCLAIMER = ("Predictions are statistical estimates based on historical patterns. They are not guaranteed "
              "future prices and cannot anticipate shocks that are absent from the data.")


# ------------------------------------------------------------------ helpers
def _lin_features(idx: pd.DatetimeIndex, t0: pd.Timestamp, seasonal: bool) -> np.ndarray:
    t = np.asarray((idx - t0).days, dtype=float) / 365.0
    cols = [t]
    if seasonal:
        doy = idx.dayofyear.values
        for k in (1, 2):
            cols += [np.sin(2 * np.pi * k * doy / 365.25), np.cos(2 * np.pi * k * doy / 365.25)]
    dow = idx.dayofweek.values
    for d in range(1, 7):
        cols.append((dow == d).astype(float))
    return np.column_stack(cols)


def _tree_row(y, date) -> list:
    last = y[-1]
    doy = date.dayofyear
    return [math.log(last / y[-2]), math.log(last / y[-4]), math.log(last / y[-8]),
            math.log(last / y[-15]), math.log(last / y[-29]),
            math.log(last / float(np.mean(y[-14:]))), math.log(last / float(np.mean(y[-28:]))),
            math.sin(2 * math.pi * doy / 365.25), math.cos(2 * math.pi * doy / 365.25), date.dayofweek]


def _make_tree_model(algo):
    if algo == "random_forest":
        return RandomForestRegressor(n_estimators=200, max_depth=8, min_samples_leaf=3, random_state=42, n_jobs=-1)
    if algo == "decision_tree":
        return DecisionTreeRegressor(max_depth=6, min_samples_leaf=5, random_state=42)
    return XGBRegressor(n_estimators=300, learning_rate=0.05, max_depth=4, subsample=0.9, random_state=42)


def _fit_predict(s: pd.Series, algo: str, h: int, ma_window: int = 14) -> dict:
    s = s.astype(float).clip(lower=1e-6)
    idx = s.index
    future = pd.date_range(idx[-1] + pd.Timedelta(days=1), periods=h, freq="D")
    out = {"lower": None, "upper": None}

    if algo == "linear_regression":
        seasonal = len(s) >= 365
        model = LinearRegression().fit(_lin_features(idx, idx[0], seasonal), s.values)
        out["pred"] = np.maximum(model.predict(_lin_features(future, idx[0], seasonal)), 0)

    elif algo in ("random_forest", "decision_tree", "xgboost"):
        if algo == "xgboost" and not HAS_XGB:
            raise ValueError("XGBoost is not installed. Run: pip install xgboost")
        if len(s) < 60:
            raise ValueError("Tree models need at least 60 observations.")
        y = s.values.tolist()
        X, t = [], []
        for i in range(29, len(y)):
            X.append(_tree_row(y[:i], idx[i]))
            t.append(math.log(y[i] / y[i - 1]))
        model = _make_tree_model(algo).fit(np.array(X), np.array(t))
        lim = 5 * float(np.std(t)) + 1e-9
        hist, preds = list(y), []
        for d in future:
            r = float(np.clip(model.predict(np.array([_tree_row(hist, d)]))[0], -lim, lim))
            hist.append(hist[-1] * math.exp(r))
            preds.append(hist[-1])
        out["pred"] = np.array(preds)

    elif algo == "moving_average":
        out["pred"] = np.repeat(float(s.iloc[-ma_window:].mean()), h)

    elif algo == "exp_smoothing":
        from statsmodels.tsa.holtwinters import ExponentialSmoothing
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            fit = ExponentialSmoothing(s.values, trend="add", damped_trend=True,
                                       initialization_method="estimated").fit()
            pred = np.asarray(fit.forecast(h))
            sd = float(np.std(fit.resid))
        steps = np.arange(1, h + 1)
        out["pred"] = pred
        out["lower"], out["upper"] = pred - 1.96 * sd * np.sqrt(steps), pred + 1.96 * sd * np.sqrt(steps)

    elif algo == "arima":
        from statsmodels.tsa.arima.model import ARIMA
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                fit = ARIMA(s.values, order=(2, 1, 2)).fit()
                fc = fit.get_forecast(h)
                out["pred"] = np.asarray(fc.predicted_mean)
                ci = np.asarray(fc.conf_int(alpha=0.05))
                out["lower"], out["upper"] = ci[:, 0], ci[:, 1]
        except Exception as exc:
            raise ValueError(f"ARIMA could not be fitted for this series ({exc}).")
    else:
        raise ValueError(f"Unknown algorithm '{algo}'.")
    return out


def _metrics(actual, pred) -> dict:
    actual, pred = np.asarray(actual, float), np.asarray(pred, float)
    mse = mean_squared_error(actual, pred)
    return {"MAE": float(mean_absolute_error(actual, pred)), "MSE": float(mse), "RMSE": float(math.sqrt(mse)),
            "R2": float(r2_score(actual, pred)) if len(actual) > 1 and np.var(actual) > 0 else None,
            "MAPE": float(np.mean(np.abs((actual - pred) / np.where(actual == 0, np.nan, actual))) * 100)}


# ------------------------------------------------------------------ public API
def run_forecast(series: pd.Series, algorithm: str, horizon: int, evaluate: bool = True) -> dict:
    s = series.astype(float)
    n = len(s)
    if n < MIN_POINTS:
        raise ValueError(f"At least {MIN_POINTS} daily observations are needed; this series has {n}.")
    res = {"algorithm": algorithm, "algorithm_label": ALGORITHMS.get(algorithm, algorithm), "horizon": horizon,
           "disclaimer": DISCLAIMER, "notes": []}
    metrics, test_rows, sigma, n_test = None, None, None, None
    if evaluate:
        n_test = max(14, int(n * 0.2))
        train, test = s.iloc[:-n_test], s.iloc[-n_test:]
        tp = _fit_predict(train, algorithm, n_test)["pred"]
        metrics = _metrics(test.values, tp)
        sigma = metrics["RMSE"]
        test_rows = [{"date": d, "actual": a, "predicted": p} for d, a, p in zip(test.index, test.values, tp)]
        res["split"] = {"method": "chronological 80/20 (no shuffling)", "train_start": train.index[0],
                        "train_end": train.index[-1], "test_start": test.index[0], "test_end": test.index[-1],
                        "train_size": len(train), "test_size": len(test)}
        if metrics["R2"] is not None and metrics["R2"] < 0:
            res["notes"].append("R² is negative on the test period: this model did worse than simply predicting the "
                                "test-period average. Treat its forecast with caution or try another algorithm.")
    full = _fit_predict(s, algorithm, horizon)
    pred = full["pred"]
    future = pd.date_range(s.index[-1] + pd.Timedelta(days=1), periods=horizon, freq="D")
    lower, upper = full["lower"], full["upper"]
    if lower is None and sigma is not None:
        half = 1.96 * sigma * np.sqrt(np.maximum(np.arange(1, horizon + 1), 7) / n_test)
        lower, upper = pred - half, pred + half
        res["notes"].append("Uncertainty band is approximate: derived from test-period RMSE, widening with horizon.")
    elif lower is not None:
        res["notes"].append("Uncertainty band is the model's own 95% interval.")
    if lower is not None:
        lower = np.maximum(lower, 0)
    last = float(s.iloc[-1])
    chg = (pred[-1] - last) / last * 100 if last else 0.0
    res.update({
        "last_date": s.index[-1], "last_value": last,
        "history": [{"date": d, "value": v} for d, v in zip(s.index[-180:], s.values[-180:])],
        "test": test_rows,
        "forecast": [{"date": d, "value": float(p), "lower": None if lower is None else float(lower[i]),
                      "upper": None if upper is None else float(upper[i])} for i, (d, p) in enumerate(zip(future, pred))],
        "metrics": metrics,
        "summary": {"predicted_final": float(pred[-1]), "predicted_mean": float(pred.mean()),
                    "predicted_min": float(pred.min()), "predicted_max": float(pred.max()),
                    "change_abs": float(pred[-1] - last), "change_pct": float(chg),
                    "direction": "Increase" if chg > 2 else "Decrease" if chg < -2 else "Stable"},
    })
    return res


def quick_forecast(series: pd.Series, horizon: int = 30) -> np.ndarray:
    """Fast linear-trend + seasonality forecast used by dashboards and aggregate series."""
    return _fit_predict(series, "linear_regression", horizon)["pred"]


def compare_algorithms(series: pd.Series, horizon: int) -> list:
    rows = []
    for key, label in ALGORITHMS.items():
        try:
            r = run_forecast(series, key, horizon, evaluate=True)
            rows.append({"algorithm": key, "label": label, **r["metrics"],
                         "predicted_final": r["summary"]["predicted_final"], "change_pct": r["summary"]["change_pct"]})
        except Exception as exc:
            rows.append({"algorithm": key, "label": label, "error": str(exc)})
    rows.sort(key=lambda r: r.get("RMSE", 1e18))
    return rows
