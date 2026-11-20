from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select
from sqlalchemy.exc import OperationalError

from app.config import APP_NAME, APP_VERSION, FRONTEND_DIR
from app.database import SessionLocal, init_db
from app.models import UploadedDataset, User
from app.routers import api
from app.services import data_service


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        init_db()
    except OperationalError as exc:
        raise RuntimeError(
            "Cannot connect to the database. Check that MySQL is running and that DB_USER / DB_PASSWORD / DB_HOST "
            f"in the .env file are correct.\nOriginal error: {exc.orig}") from exc
    with SessionLocal() as db:
        if not db.scalar(select(User)):
            db.add(User(username="admin", full_name="Admin Analyst", email="admin@example.com", role="Administrator"))
            db.commit()
        if not db.scalar(select(UploadedDataset)):
            print("First run: loading simulated sample dataset (a few seconds)...")
            data_service.load_sample(db)
    yield


app = FastAPI(title=APP_NAME, version=APP_VERSION, lifespan=lifespan,
              description="Data Mining project: price prediction, trend analysis and price optimization.")
app.include_router(api.router)
app.mount("/static", StaticFiles(directory=FRONTEND_DIR / "static"), name="static")


@app.exception_handler(data_service.DataError)
async def data_error(_: Request, exc: data_service.DataError):
    return JSONResponse({"detail": str(exc)}, status_code=400)


@app.exception_handler(ValueError)
async def value_error(_: Request, exc: ValueError):
    return JSONResponse({"detail": str(exc)}, status_code=400)


@app.exception_handler(RequestValidationError)
async def validation_error(_: Request, exc: RequestValidationError):
    msgs = []
    for e in exc.errors():
        field = ".".join(str(x) for x in e["loc"] if x not in ("body", "query"))
        msgs.append(f"{field}: {e['msg']}" if field else e["msg"])
    return JSONResponse({"detail": "; ".join(msgs)}, status_code=422)


@app.exception_handler(Exception)
async def unexpected(_: Request, exc: Exception):
    return JSONResponse({"detail": f"Unexpected server error: {exc}"}, status_code=500)


@app.get("/", include_in_schema=False)
def home():
    return FileResponse(FRONTEND_DIR / "index.html")
