import datetime as dt
import math

import numpy as np
import pandas as pd
from fastapi.responses import JSONResponse


def clean(o):
    """Convert numpy / pandas objects to JSON-safe Python values (NaN -> None)."""
    if o is None or o is pd.NaT:
        return None
    if isinstance(o, dict):
        return {str(k): clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple, set)):
        return [clean(v) for v in o]
    if isinstance(o, pd.DataFrame):
        return clean(o.to_dict("records"))
    if isinstance(o, (pd.Series, np.ndarray, pd.Index)):
        return clean(list(o))
    if isinstance(o, (bool, np.bool_)):
        return bool(o)
    if isinstance(o, (int, np.integer)):
        return int(o)
    if isinstance(o, (float, np.floating)):
        f = float(o)
        return None if (math.isnan(f) or math.isinf(f)) else round(f, 4)
    if isinstance(o, (pd.Timestamp, dt.datetime, dt.date)):
        return o.strftime("%Y-%m-%d")
    return o


def ok(o, status: int = 200) -> JSONResponse:
    return JSONResponse(clean(o), status_code=status)
