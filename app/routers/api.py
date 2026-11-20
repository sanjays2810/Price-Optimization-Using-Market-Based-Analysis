import json
import re
import uuid
from pathlib import Path

import pandas as pd
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import (ALLOWED_EXTENSIONS, APP_NAME, APP_VERSION, CURRENCY, DATABASE_URL, MAX_UPLOAD_MB,
                        REPORT_DIR, SAMPLE_DIR, UPLOAD_DIR)
from app.database import get_db
from app.ml import predictor
from app.models import (AnalysisReport, MarketData, OptimizationResult, PredictionResult, Product, UploadedDataset, User)
from app.schemas.schemas import CommitRequest, OptimizeRequest, PredictRequest, ReportRequest
from app.services import analytics as an
from app.services import data_service as ds_svc
from app.services import optimizer, reports
from app.utils.jsonutil import ok

router = APIRouter(prefix="/api")


def ctx(db: Session = Depends(get_db)):
    ds = ds_svc.active_dataset(db)
    if not ds:
        raise HTTPException(404, "No active dataset. Go to Dataset Management and load the sample dataset or upload a file.")
    return ds, ds_svc.load_df(db, ds.id)


def _ds_dict(d: UploadedDataset):
    return {"id": d.id, "name": d.name, "filename": d.filename, "source": d.source, "rows_raw": d.rows_raw,
            "rows_clean": d.rows_clean, "date_min": d.date_min, "date_max": d.date_max, "is_active": d.is_active,
            "created_at": d.created_at}


# ------------------------------------------------------------------ meta
@router.get("/health")
def health(db: Session = Depends(get_db)):
    db.execute(select(1))
    return {"status": "ok", "application": APP_NAME, "version": APP_VERSION, "database": "connected"}


@router.get("/meta")
def meta(db: Session = Depends(get_db)):
    ds = ds_svc.active_dataset(db)
    out = {"app": APP_NAME, "version": APP_VERSION, "currency": CURRENCY, "algorithms": predictor.ALGORITHMS,
           "horizons": [7, 15, 30, 60, 90], "report_types": reports.REPORT_TYPES, "dataset": None, "products": [], "categories": [],
           "database": "SQLite (testing)" if DATABASE_URL.startswith("sqlite") else "MySQL",
           "user": None}
    u = db.scalar(select(User).order_by(User.id))
    if u:
        out["user"] = {"name": u.full_name, "role": u.role, "email": u.email}
    if ds:
        out["dataset"] = _ds_dict(ds)
        rows = db.execute(select(Product.id, Product.name, Product.product_code).where(Product.dataset_id == ds.id).order_by(Product.name)).all()
        df = ds_svc.load_df(db, ds.id)
        cat = df.drop_duplicates("product_id").set_index("product_id").category.to_dict()
        out["products"] = [{"id": r.id, "name": r.name, "code": r.product_code, "category": cat.get(r.id, "")} for r in rows]
        out["categories"] = sorted(set(cat.values()))
    return ok(out)


@router.get("/search")
def search(q: str = Query(min_length=1, max_length=50), db: Session = Depends(get_db)):
    ds = ds_svc.active_dataset(db)
    if not ds:
        return ok([])
    rows = db.execute(select(Product.id, Product.name, Product.product_code).where(
        Product.dataset_id == ds.id, Product.name.ilike(f"%{q}%")).limit(8)).all()
    return ok([{"id": r.id, "name": r.name, "code": r.product_code} for r in rows])


@router.get("/notifications")
def notifications(c=Depends(ctx)):
    return ok(an.notifications(c[1]))


# ------------------------------------------------------------------ datasets
@router.get("/datasets")
def list_datasets(db: Session = Depends(get_db)):
    rows = db.scalars(select(UploadedDataset).order_by(UploadedDataset.id.desc())).all()
    return ok([_ds_dict(r) for r in rows])


@router.post("/datasets/sample")
def load_sample(db: Session = Depends(get_db)):
    d = ds_svc.load_sample(db)
    return ok({"message": "Simulated sample dataset loaded.", "dataset": _ds_dict(d)})


@router.get("/datasets/sample-file/{fmt}")
def sample_file(fmt: str):
    if fmt not in ("csv", "xlsx"):
        raise HTTPException(400, "Format must be csv or xlsx.")
    p = SAMPLE_DIR / f"sample_market_data.{fmt}"
    if not p.exists():
        from app.services.sample_data import write_sample_files
        write_sample_files()
    return FileResponse(p, filename=p.name)


@router.post("/datasets/upload")
async def upload(file: UploadFile = File(...)):
    ext = Path(file.filename or "").suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(400, f"Unsupported file type '{ext}'. Upload a .csv, .xlsx or .xls file.")
    content = await file.read()
    if len(content) > MAX_UPLOAD_MB * 1024 * 1024:
        raise HTTPException(400, f"File is larger than {MAX_UPLOAD_MB} MB.")
    if not content:
        raise HTTPException(400, "The uploaded file is empty.")
    token = uuid.uuid4().hex
    safe = re.sub(r"[^A-Za-z0-9._-]", "_", file.filename)
    path = UPLOAD_DIR / f"{token}_{safe}"
    path.write_bytes(content)
    try:
        raw = ds_svc.read_file(path)
        clean_df, rep = ds_svc.clean_dataset(raw)
    except ds_svc.DataError:
        path.unlink(missing_ok=True)
        raise
    return ok({"token": token, "filename": file.filename, "report": rep,
               "raw_preview": {"columns": [str(c) for c in raw.columns], "rows": raw.head(10).astype(object).where(raw.head(10).notna(), None).values.tolist()},
               "clean_preview": {"columns": list(clean_df.columns), "rows": clean_df.head(15).assign(date=lambda x: x.date.dt.strftime("%Y-%m-%d")).values.tolist()}})


@router.post("/datasets/commit")
def commit(req: CommitRequest, db: Session = Depends(get_db)):
    matches = list(UPLOAD_DIR.glob(f"{req.token}_*"))
    if not matches:
        raise HTTPException(404, "Upload not found or expired. Upload the file again.")
    path = matches[0]
    raw = ds_svc.read_file(path)
    df, rep = ds_svc.clean_dataset(raw)
    name = path.name[len(req.token) + 1:]
    d = ds_svc.save_dataset(db, df, req.name.strip(), name, "upload", rep)
    return ok({"message": f"Saved {len(df):,} cleaned rows to the database.", "dataset": _ds_dict(d)})


@router.post("/datasets/{dataset_id}/activate")
def activate(dataset_id: int, db: Session = Depends(get_db)):
    ds_svc.activate_dataset(db, dataset_id)
    return ok({"message": "Dataset activated."})


@router.delete("/datasets/{dataset_id}")
def delete(dataset_id: int, db: Session = Depends(get_db)):
    if not db.get(UploadedDataset, dataset_id):
        raise HTTPException(404, "Dataset not found.")
    ds_svc.delete_dataset(db, dataset_id)
    return ok({"message": "Dataset deleted."})


@router.get("/datasets/{dataset_id}/report")
def dataset_report(dataset_id: int, db: Session = Depends(get_db)):
    d = db.get(UploadedDataset, dataset_id)
    if not d:
        raise HTTPException(404, "Dataset not found.")
    return ok({"dataset": _ds_dict(d), "report": json.loads(d.validation_report or "{}")})


@router.get("/datasets/{dataset_id}/data")
def dataset_data(dataset_id: int, page: int = Query(1, ge=1), page_size: int = Query(20, ge=5, le=100),
                 product_id: int | None = None, db: Session = Depends(get_db)):
    if not db.get(UploadedDataset, dataset_id):
        raise HTTPException(404, "Dataset not found.")
    df = ds_svc.load_df(db, dataset_id)
    if product_id:
        df = df[df.product_id == product_id]
    total = len(df)
    part = df.iloc[(page - 1) * page_size: page * page_size].drop(columns=["product_id"])
    return ok({"columns": list(part.columns), "rows": part.assign(date=part.date.dt.strftime("%Y-%m-%d")).values.tolist(),
               "total": total, "page": page, "pages": max(1, -(-total // page_size))})


# ------------------------------------------------------------------ analytics
@router.get("/dashboard")
def dashboard(c=Depends(ctx)):
    return ok({"dataset": _ds_dict(c[0]), **an.dashboard(c[1])})


@router.get("/eda")
def eda(product_id: int | None = None, category: str | None = None, c=Depends(ctx)):
    return ok(an.eda(c[1], product_id, category))


@router.get("/eda/clusters")
def clusters(k: int = Query(3, ge=2, le=6), c=Depends(ctx)):
    return ok(an.clusters(c[1], k))


@router.get("/trends")
def trends(product_id: int | None = None, c=Depends(ctx)):
    return ok(an.trends(c[1], product_id))


@router.get("/demand-supply")
def demand_supply(product_id: int | None = None, category: str | None = None, c=Depends(ctx)):
    return ok(an.demand_supply(c[1], product_id, category))


@router.get("/competitors")
def competitors(product_id: int | None = None, category: str | None = None, c=Depends(ctx)):
    return ok(an.competitors(c[1], product_id, category))


@router.get("/profit")
def profit(product_id: int | None = None, category: str | None = None, c=Depends(ctx)):
    return ok(an.profit(c[1], product_id, category))


# ------------------------------------------------------------------ prediction
def _series(df, product_id):
    g = df[df.product_id == product_id]
    if g.empty:
        raise HTTPException(404, "Product not found in the active dataset.")
    return g, an.daily(g, "historical_price")


@router.post("/predict")
def predict(req: PredictRequest, c=Depends(ctx), db: Session = Depends(get_db)):
    ds, df = c
    g, s = _series(df, req.product_id)
    r = predictor.run_forecast(s, req.algorithm, req.horizon)
    r["product"] = {"id": req.product_id, "name": g.product_name.iloc[0], "category": g.category.iloc[0]}
    from app.utils.jsonutil import clean
    db.add(PredictionResult(dataset_id=ds.id, product_id=req.product_id, algorithm=req.algorithm, horizon_days=req.horizon,
                            metrics=json.dumps(clean(r["metrics"])), forecast=json.dumps(clean(r["forecast"]))))
    db.commit()
    return ok(r)


@router.get("/predict/compare")
def predict_compare(product_id: int, horizon: int = Query(30), c=Depends(ctx)):
    if horizon not in (7, 15, 30, 60, 90):
        raise HTTPException(422, "horizon must be 7, 15, 30, 60 or 90 days")
    _, s = _series(c[1], product_id)
    return ok({"rows": predictor.compare_algorithms(s, horizon), "note": "Ranked by RMSE on the chronological test period (lower is better)."})


# ------------------------------------------------------------------ optimization
@router.get("/optimize/defaults")
def opt_defaults(product_id: int, c=Depends(ctx)):
    return ok(optimizer.defaults(c[1], product_id))


@router.post("/optimize")
def optimize(req: OptimizeRequest, c=Depends(ctx), db: Session = Depends(get_db)):
    ds, df = c
    inputs = req.model_dump(exclude={"product_id", "allow_loss", "min_margin_pct", "target_margin_pct", "horizon_days"})
    r = optimizer.optimize(df, req.product_id, inputs, req.allow_loss, req.min_margin_pct, req.target_margin_pct, req.horizon_days)
    from app.utils.jsonutil import clean
    db.add(OptimizationResult(dataset_id=ds.id, product_id=req.product_id, inputs=json.dumps(clean(r["inputs_used"])),
                              result=json.dumps(clean({k: r[k] for k in ("mode", "current", "recommended", "warnings")}))))
    db.commit()
    return ok(r)


# ------------------------------------------------------------------ reports
@router.post("/reports")
def make_report(req: ReportRequest, c=Depends(ctx), db: Session = Depends(get_db)):
    if req.report_type not in reports.REPORT_TYPES:
        raise HTTPException(422, "Unknown report type.")
    ds, df = c
    rep = json.loads(ds.validation_report or "{}")
    path = reports.generate(req.report_type, req.file_format, df, ds, rep, product_id=req.product_id,
                            algorithm=req.algorithm, horizon=req.horizon)
    row = AnalysisReport(dataset_id=ds.id, report_type=req.report_type, file_format=req.file_format, file_name=path.name)
    db.add(row)
    db.commit()
    return ok({"id": row.id, "file_name": path.name, "download_url": f"/api/reports/download/{row.id}"})


@router.get("/reports/history")
def report_history(db: Session = Depends(get_db)):
    rows = db.scalars(select(AnalysisReport).order_by(AnalysisReport.id.desc()).limit(25)).all()
    return ok([{"id": r.id, "type": reports.REPORT_TYPES.get(r.report_type, r.report_type), "format": r.file_format,
                "file_name": r.file_name, "created_at": r.created_at} for r in rows])


@router.get("/reports/download/{report_id}")
def download_report(report_id: int, db: Session = Depends(get_db)):
    r = db.get(AnalysisReport, report_id)
    path = REPORT_DIR / r.file_name if r else None
    if not r or not path.exists():
        raise HTTPException(404, "Report file not found.")
    return FileResponse(path, filename=r.file_name)
