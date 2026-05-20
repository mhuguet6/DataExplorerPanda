"""
FastAPI service for the Upload & Clean tab.

Exposes three endpoints:
  POST /api/upload                   — accept a CSV, return suggestions + preview
  POST /api/clean                    — apply accepted + custom steps, return preview
  GET  /api/download/{session_id}    — download the cleaned CSV

Session state is held in-memory in `SESSIONS` and drops on restart. That's
fine for local single-user use; a persistent store would be overkill.

Run with:
    cd backend
    source .venv/bin/activate
    uvicorn src.api:app --reload --port 8000
"""

from __future__ import annotations

import io
import json
import uuid
from typing import Any, Optional

import pandas as pd
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from suggest_clean import apply_steps, suggest

PREVIEW_ROWS = 20
MAX_UPLOAD_BYTES = 25 * 1024 * 1024  # 25 MB

app = FastAPI(title="Data Explorer Panda — Upload & Clean")

# The frontend runs on localhost:5173 by default. CORS is only needed when the
# browser hits the API directly; if you proxy /api/* through Vite, this is a
# no-op. Kept open to localhost so both modes work.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_methods=["*"],
    allow_headers=["*"],
)

# session_id -> {"raw": DataFrame, "cleaned": DataFrame | None, "filename": str}
SESSIONS: dict[str, dict[str, Any]] = {}


# ---------------------------------------------------------------------------
# Request/response models
# ---------------------------------------------------------------------------

class CleanStep(BaseModel):
    action: str
    column: Optional[str] = None
    value: Optional[Any] = None


class CleanRequest(BaseModel):
    session_id: str
    steps: list[CleanStep] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.post("/api/upload")
async def upload(file: UploadFile = File(...)) -> dict[str, Any]:
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Please upload a .csv file.")

    payload = await file.read()
    if len(payload) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File exceeds {MAX_UPLOAD_BYTES // (1024 * 1024)} MB limit.",
        )

    try:
        df = pd.read_csv(io.BytesIO(payload))
    except Exception as exc:
        raise HTTPException(
            status_code=400, detail=f"Could not parse CSV: {exc}"
        ) from exc

    if df.empty:
        raise HTTPException(status_code=400, detail="CSV is empty.")

    session_id = uuid.uuid4().hex
    SESSIONS[session_id] = {"raw": df, "cleaned": None, "filename": file.filename}

    return {
        "session_id": session_id,
        "filename": file.filename,
        "shape": list(df.shape),
        "columns": list(df.columns),
        "dtypes": {col: str(dtype) for col, dtype in df.dtypes.items()},
        "missing": _missing_counts(df),
        "raw_preview": _df_to_records(df.head(PREVIEW_ROWS)),
        "suggestions": suggest(df),
    }


@app.post("/api/clean")
def clean(req: CleanRequest) -> dict[str, Any]:
    session = SESSIONS.get(req.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Unknown session_id.")

    raw: pd.DataFrame = session["raw"]
    steps_dicts = [s.model_dump() for s in req.steps]
    cleaned, log = apply_steps(raw, steps_dicts)

    session["cleaned"] = cleaned

    return {
        "session_id": req.session_id,
        "shape_before": list(raw.shape),
        "shape_after": list(cleaned.shape),
        "missing_after": _missing_counts(cleaned),
        "columns_after": list(cleaned.columns),
        "preview": _df_to_records(cleaned.head(PREVIEW_ROWS)),
        "log": log,
        "download_url": f"/api/download/{req.session_id}",
    }


@app.get("/api/download/{session_id}")
def download(session_id: str) -> StreamingResponse:
    session = SESSIONS.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Unknown session_id.")
    cleaned = session.get("cleaned")
    if cleaned is None:
        raise HTTPException(status_code=400, detail="Session has not been cleaned yet.")

    buffer = io.StringIO()
    cleaned.to_csv(buffer, index=False)
    buffer.seek(0)

    original = session["filename"]
    stem = original.rsplit(".", 1)[0] if "." in original else original
    download_name = f"{stem}_cleaned.csv"

    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{download_name}"'},
    )


@app.get("/api/health")
def health() -> dict[str, Any]:
    return {"ok": True, "sessions": len(SESSIONS)}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _missing_counts(df: pd.DataFrame) -> dict[str, int]:
    missing = df.isna().sum()
    return {col: int(n) for col, n in missing.items() if n > 0}


def _df_to_records(df: pd.DataFrame) -> list[dict[str, Any]]:
    """
    Convert a DataFrame to JSON-safe records.

    `df.to_dict()` leaves NaN as float('nan') and numpy types in place; both
    break json.dumps. Round-tripping via to_json normalizes everything.
    """
    return json.loads(df.to_json(orient="records", date_format="iso"))
