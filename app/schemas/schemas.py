from typing import Optional

from pydantic import BaseModel, Field, field_validator

from app.ml.predictor import ALGORITHMS


class PredictRequest(BaseModel):
    product_id: int = Field(gt=0)
    algorithm: str
    horizon: int

    @field_validator("algorithm")
    @classmethod
    def _algo(cls, v):
        if v not in ALGORITHMS:
            raise ValueError(f"algorithm must be one of: {', '.join(ALGORITHMS)}")
        return v

    @field_validator("horizon")
    @classmethod
    def _h(cls, v):
        if v not in (7, 15, 30, 60, 90):
            raise ValueError("horizon must be 7, 15, 30, 60 or 90 days")
        return v


class OptimizeRequest(BaseModel):
    product_id: int = Field(gt=0)
    current_price: Optional[float] = Field(default=None, gt=0)
    cost_price: Optional[float] = Field(default=None, gt=0)
    competitor_price: Optional[float] = Field(default=None, gt=0)
    demand_qty: Optional[float] = Field(default=None, gt=0)
    supply_qty: Optional[float] = Field(default=None, gt=0)
    inventory: Optional[float] = Field(default=None, ge=0)
    expected_demand: Optional[float] = Field(default=None, gt=0)
    allow_loss: bool = False
    min_margin_pct: float = Field(default=5.0, ge=0, le=100)
    target_margin_pct: float = Field(default=25.0, ge=0, le=300)
    horizon_days: int = Field(default=30, ge=1, le=365)


class CommitRequest(BaseModel):
    token: str = Field(pattern=r"^[0-9a-f]{32}$")
    name: str = Field(min_length=2, max_length=120)


class ReportRequest(BaseModel):
    report_type: str
    file_format: str = "pdf"
    product_id: Optional[int] = None
    algorithm: str = "linear_regression"
    horizon: int = 30

    @field_validator("file_format")
    @classmethod
    def _f(cls, v):
        if v not in ("pdf", "xlsx"):
            raise ValueError("file_format must be pdf or xlsx")
        return v
