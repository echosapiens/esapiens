"""
File Upload & Parsing — E.sapiens v2.

Provides:
  POST /upload — multipart form upload with file + session_id
  File parsers for CSV, TSV, JSON, XLSX
  Preview generation (first 20 rows / 100 entries)
  Workspace-based file storage
"""

import json
import os
import uuid
from pathlib import Path
from typing import Any, Optional

import pandas as pd
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.security import HTTPAuthorizationCredentials

from auth import get_current_user, security_scheme
from storage import get_storage

upload_router = APIRouter(tags=["upload"])

# ═══════════════════════════════════════════════════════════════════════════
# Configuration
# ═══════════════════════════════════════════════════════════════════════════

MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB
ALLOWED_EXTENSIONS = {".csv", ".tsv", ".json", ".xlsx"}
PREVIEW_ROWS = 20
PREVIEW_JSON_ENTRIES = 100


# ═══════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════

def _detect_format(filename: str) -> str:
    """Return normalized format string from file extension."""
    ext = Path(filename).suffix.lower()
    mapping = {
        ".csv": "csv",
        ".tsv": "tsv",
        ".json": "json",
        ".xlsx": "xlsx",
    }
    return mapping.get(ext, "")


def _parse_csv(filepath: Path) -> dict[str, Any]:
    """Parse a CSV file and return preview data."""
    try:
        df = pd.read_csv(filepath)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Failed to parse CSV: {e}",
        )
    preview = df.head(PREVIEW_ROWS).to_dict(orient="records")
    # Convert numpy/pandas types to native Python for JSON serialization
    preview = json.loads(json.dumps(preview, default=str))
    return {
        "rows": len(df),
        "columns": list(df.columns),
        "preview": preview,
    }


def _parse_tsv(filepath: Path) -> dict[str, Any]:
    """Parse a TSV file and return preview data."""
    try:
        df = pd.read_csv(filepath, sep="\t")
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Failed to parse TSV: {e}",
        )
    preview = df.head(PREVIEW_ROWS).to_dict(orient="records")
    preview = json.loads(json.dumps(preview, default=str))
    return {
        "rows": len(df),
        "columns": list(df.columns),
        "preview": preview,
    }


def _parse_json(filepath: Path) -> dict[str, Any]:
    """Parse a JSON file and return preview data."""
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Failed to parse JSON: {e}",
        )

    if isinstance(data, list):
        # List of records (most common tabular case)
        rows = len(data)
        if rows > 0 and isinstance(data[0], dict):
            # Convert list of dicts to DataFrame for column extraction
            df = pd.DataFrame(data)
            columns = list(df.columns)
            preview = data[:PREVIEW_JSON_ENTRIES]
            preview = json.loads(json.dumps(preview, default=str))
        else:
            # List of primitives
            columns = ["value"]
            preview = [{"value": v} for v in data[:PREVIEW_JSON_ENTRIES]]
            preview = json.loads(json.dumps(preview, default=str))
        return {
            "rows": rows,
            "columns": columns,
            "preview": preview,
        }
    elif isinstance(data, dict):
        # Single dict — treat keys as columns, values as one row
        columns = list(data.keys())
        rows = 1
        preview = [json.loads(json.dumps({k: data[k]}, default=str)) for k in list(data.keys())[:PREVIEW_JSON_ENTRIES]]
        # Actually, for a dict, show as a single record
        preview = [json.loads(json.dumps(data, default=str))]
        return {
            "rows": rows,
            "columns": columns,
            "preview": preview,
        }
    else:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="JSON root must be a list of records or a dictionary.",
        )


def _parse_xlsx(filepath: Path) -> dict[str, Any]:
    """Parse an XLSX file and return preview data."""
    try:
        df = pd.read_excel(filepath, engine="openpyxl")
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Failed to parse XLSX: {e}",
        )
    preview = df.head(PREVIEW_ROWS).to_dict(orient="records")
    preview = json.loads(json.dumps(preview, default=str))
    return {
        "rows": len(df),
        "columns": list(df.columns),
        "preview": preview,
    }


_PARSERS = {
    "csv": _parse_csv,
    "tsv": _parse_tsv,
    "json": _parse_json,
    "xlsx": _parse_xlsx,
}


def _generate_summary(filename: str, fmt: str, parsed: dict[str, Any]) -> str:
    """Generate a text summary of parsed file data for prepending to queries."""
    rows = parsed["rows"]
    columns = parsed["columns"]
    preview = parsed["preview"]
    lines = [
        f"[Attached file: {filename} ({fmt.upper()}, {rows} rows, {len(columns)} columns: {', '.join(columns)})]",
        "Preview (first rows):",
    ]
    for row in preview[:PREVIEW_ROWS]:
        lines.append("  " + ", ".join(f"{k}={v}" for k, v in row.items()))
    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════════
# Upload endpoint
# ═══════════════════════════════════════════════════════════════════════════


@upload_router.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    session_id: str = Form("default"),
    current_user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    """
    Upload a data file (CSV, TSV, JSON, or XLSX) and return a parsed preview.

    The file is saved to the user's workspace and parsed to extract:
      - Row count
      - Column names
      - Preview data (first 20 rows / 100 entries)

    Returns a JSON response with file_id, metadata, and preview.
    """
    # ── Validate file extension ──────────────────────────────────────────
    filename = file.filename or "unknown"
    fmt = _detect_format(filename)
    if fmt not in _PARSERS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file format. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
        )

    # ── Validate file size ───────────────────────────────────────────────
    contents = await file.read()
    if len(contents) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File too large. Maximum size: {MAX_FILE_SIZE // (1024 * 1024)} MB.",
        )

    # ── Save file to workspace ───────────────────────────────────────────
    storage = get_storage()
    user_id = current_user["id"]
    workspace = storage.ensure_workspace(user_id, session_id)
    upload_dir = workspace / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)

    # Generate unique file_id to avoid collisions
    file_id = f"upl_{uuid.uuid4().hex[:8]}"
    safe_filename = "".join(c if c.isalnum() or c in ".-_ " else "_" for c in filename)
    # Prepend file_id to ensure uniqueness
    stored_name = f"{file_id}_{safe_filename}"
    filepath = upload_dir / stored_name

    with open(filepath, "wb") as f:
        f.write(contents)

    # ── Parse the file ────────────────────────────────────────────────────
    parser = _PARSERS[fmt]
    try:
        parsed = parser(filepath)
    except HTTPException:
        # Remove file if parsing fails
        filepath.unlink(missing_ok=True)
        raise

    # ── Build response ────────────────────────────────────────────────────
    return {
        "file_id": file_id,
        "filename": filename,
        "format": fmt,
        "rows": parsed["rows"],
        "columns": parsed["columns"],
        "preview": parsed["preview"],
        "session_id": session_id,
        "filepath": str(filepath),
        "summary": _generate_summary(filename, fmt, parsed),
    }