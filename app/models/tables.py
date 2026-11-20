from datetime import date, datetime

from sqlalchemy import (Boolean, Date, DateTime, Double, ForeignKey, Index, Integer,
                        String, Text, UniqueConstraint, func)
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    full_name: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str] = mapped_column(String(120), nullable=False)
    role: Mapped[str] = mapped_column(String(30), default="analyst")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.current_timestamp())


class Category(Base):
    __tablename__ = "categories"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.current_timestamp())


class UploadedDataset(Base):
    __tablename__ = "uploaded_datasets"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    source: Mapped[str] = mapped_column(String(20), nullable=False)  # sample | upload
    rows_raw: Mapped[int] = mapped_column(Integer, default=0)
    rows_clean: Mapped[int] = mapped_column(Integer, default=0)
    date_min: Mapped[date] = mapped_column(Date, nullable=True)
    date_max: Mapped[date] = mapped_column(Date, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False)
    validation_report: Mapped[str] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.current_timestamp())


class Product(Base):
    __tablename__ = "products"
    __table_args__ = (UniqueConstraint("dataset_id", "product_code", name="uq_product_dataset_code"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    dataset_id: Mapped[int] = mapped_column(ForeignKey("uploaded_datasets.id", ondelete="CASCADE"), index=True)
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id"), index=True)
    product_code: Mapped[str] = mapped_column(String(60), nullable=False)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.current_timestamp())


class MarketData(Base):
    __tablename__ = "market_data"
    __table_args__ = (Index("ix_market_ds_prod_date", "dataset_id", "product_id", "record_date"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    dataset_id: Mapped[int] = mapped_column(ForeignKey("uploaded_datasets.id", ondelete="CASCADE"))
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"))
    record_date: Mapped[date] = mapped_column(Date, nullable=False)
    historical_price: Mapped[float] = mapped_column(Double)
    cost_price: Mapped[float] = mapped_column(Double)
    selling_price: Mapped[float] = mapped_column(Double)
    demand_qty: Mapped[float] = mapped_column(Double)
    supply_qty: Mapped[float] = mapped_column(Double)
    competitor_price: Mapped[float] = mapped_column(Double)
    sales_qty: Mapped[float] = mapped_column(Double)
    inventory: Mapped[float] = mapped_column(Double)
    season: Mapped[str] = mapped_column(String(40), nullable=True)
    location: Mapped[str] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.current_timestamp())


class CompetitorPrice(Base):
    __tablename__ = "competitor_prices"
    __table_args__ = (Index("ix_comp_ds_prod_date", "dataset_id", "product_id", "record_date"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    dataset_id: Mapped[int] = mapped_column(ForeignKey("uploaded_datasets.id", ondelete="CASCADE"))
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"))
    record_date: Mapped[date] = mapped_column(Date, nullable=False)
    location: Mapped[str] = mapped_column(String(100), nullable=True)
    competitor_price: Mapped[float] = mapped_column(Double)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.current_timestamp())


class SalesRecord(Base):
    __tablename__ = "sales_records"
    __table_args__ = (Index("ix_sales_ds_prod_date", "dataset_id", "product_id", "record_date"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    dataset_id: Mapped[int] = mapped_column(ForeignKey("uploaded_datasets.id", ondelete="CASCADE"))
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"))
    record_date: Mapped[date] = mapped_column(Date, nullable=False)
    sales_qty: Mapped[float] = mapped_column(Double)
    revenue: Mapped[float] = mapped_column(Double)
    total_cost: Mapped[float] = mapped_column(Double)
    profit: Mapped[float] = mapped_column(Double)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.current_timestamp())


class PredictionResult(Base):
    __tablename__ = "prediction_results"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    dataset_id: Mapped[int] = mapped_column(ForeignKey("uploaded_datasets.id", ondelete="CASCADE"), index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), index=True)
    algorithm: Mapped[str] = mapped_column(String(40))
    horizon_days: Mapped[int] = mapped_column(Integer)
    metrics: Mapped[str] = mapped_column(Text, nullable=True)
    forecast: Mapped[str] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.current_timestamp())


class OptimizationResult(Base):
    __tablename__ = "optimization_results"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    dataset_id: Mapped[int] = mapped_column(ForeignKey("uploaded_datasets.id", ondelete="CASCADE"), index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), index=True)
    inputs: Mapped[str] = mapped_column(Text, nullable=True)
    result: Mapped[str] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.current_timestamp())


class AnalysisReport(Base):
    __tablename__ = "analysis_reports"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    dataset_id: Mapped[int] = mapped_column(Integer, nullable=True)
    report_type: Mapped[str] = mapped_column(String(50))
    file_format: Mapped[str] = mapped_column(String(10))
    file_name: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.current_timestamp())
