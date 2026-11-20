import os
from pathlib import Path
from urllib.parse import quote_plus

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

APP_NAME = "Price Optimization and Future Market Trend Analysis System"
APP_VERSION = "1.0.0"
CURRENCY = "₹"

FRONTEND_DIR = BASE_DIR / "frontend"
UPLOAD_DIR = BASE_DIR / "data" / "uploads"
SAMPLE_DIR = BASE_DIR / "data" / "sample"
REPORT_DIR = BASE_DIR / "data" / "reports"

MAX_UPLOAD_MB = 25
ALLOWED_EXTENSIONS = {".csv", ".xlsx", ".xls"}

DB_USER = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "3306")
DB_NAME = os.getenv("DB_NAME", "price_optimization_db")

DATABASE_URL = os.getenv("DATABASE_URL") or (
    f"mysql+pymysql://{DB_USER}:{quote_plus(DB_PASSWORD)}@{DB_HOST}:{DB_PORT}/{DB_NAME}?charset=utf8mb4"
)

for folder in (UPLOAD_DIR, SAMPLE_DIR, REPORT_DIR):
    folder.mkdir(parents=True, exist_ok=True)
