"""Run: python -m pytest tests -q   (uses a temporary SQLite DB, no MySQL needed)"""
import os
import tempfile

os.environ["DATABASE_URL"] = f"sqlite:///{tempfile.gettempdir()}/po_test.db"
if os.path.exists(f"{tempfile.gettempdir()}/po_test.db"):
    os.remove(f"{tempfile.gettempdir()}/po_test.db")

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402


def test_full_flow():
    with TestClient(app) as c:
        assert c.get("/api/health").json()["status"] == "ok"
        meta = c.get("/api/meta").json()
        assert len(meta["products"]) == 24
        pid = meta["products"][0]["id"]
        for url in ["/api/dashboard", "/api/eda", "/api/eda/clusters", f"/api/trends?product_id={pid}", "/api/demand-supply",
                    "/api/competitors", "/api/profit", "/api/notifications", f"/api/optimize/defaults?product_id={pid}"]:
            r = c.get(url)
            assert r.status_code == 200, (url, r.text)
        for algo in meta["algorithms"]:
            r = c.post("/api/predict", json={"product_id": pid, "algorithm": algo, "horizon": 30})
            assert r.status_code == 200, (algo, r.text)
            assert r.json()["metrics"]["RMSE"] > 0
        assert c.post("/api/predict", json={"product_id": pid, "algorithm": "bad", "horizon": 30}).status_code == 422
        o = c.post("/api/optimize", json={"product_id": pid}).json()
        assert o["recommended"]["best_price"] >= o["recommended"]["minimum_profitable_price"]
        assert c.post("/api/optimize", json={"product_id": pid, "cost_price": -5}).status_code == 422
        for t in meta["report_types"]:
            for f in ("pdf", "xlsx"):
                r = c.post("/api/reports", json={"report_type": t, "file_format": f, "product_id": pid if t != "dataset_analysis" else None})
                assert r.status_code == 200, (t, f, r.text)
                assert c.get(r.json()["download_url"]).status_code == 200
        bad = c.post("/api/datasets/upload", files={"file": ("x.csv", b"a,b\n1,2\n", "text/csv")})
        assert bad.status_code == 400 and "Missing required" in bad.json()["detail"]
        sample = c.get("/api/datasets/sample-file/csv").content
        up = c.post("/api/datasets/upload", files={"file": ("my.csv", sample, "text/csv")}).json()
        assert up["report"]["rows_clean"] > 17000
        saved = c.post("/api/datasets/commit", json={"token": up["token"], "name": "My upload"})
        assert saved.status_code == 200
        assert c.get("/api/meta").json()["dataset"]["name"] == "My upload"
