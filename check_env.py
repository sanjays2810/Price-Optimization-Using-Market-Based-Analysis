"""Run:  python check_env.py   - verifies Python, libraries and the MySQL connection."""
import importlib
import sys

print("Python", sys.version.split()[0])
bad = 0
for m in ["fastapi", "uvicorn", "sqlalchemy", "pymysql", "pydantic", "multipart", "dotenv", "pandas", "numpy", "scipy",
          "sklearn", "statsmodels", "openpyxl", "xlrd", "reportlab"]:
    try:
        mod = importlib.import_module(m)
        print(f"  OK   {m} {getattr(mod, '__version__', '')}")
    except Exception as e:
        bad += 1
        print(f"  FAIL {m}: {e}")
try:
    import xgboost  # noqa
    print("  OK   xgboost (optional) - XGBoost algorithm enabled")
except Exception:
    print("  --   xgboost not installed (optional)")
from app.config import DATABASE_URL
from app.database import ensure_database, engine
from sqlalchemy import text
try:
    ensure_database()
    with engine.connect() as c:
        c.execute(text("SELECT 1"))
    print("  OK   database connection:", DATABASE_URL.split("@")[-1])
except Exception as e:
    bad += 1
    print("  FAIL database connection:", e, "\n       Check MySQL is running and DB_PASSWORD in the .env file.")
print("\nAll good." if not bad else f"\n{bad} problem(s) found.")
