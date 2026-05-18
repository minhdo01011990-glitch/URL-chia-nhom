"""Đọc dữ liệu từ CSV, Excel, hoặc Google Sheets vào pandas DataFrame."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Optional

import pandas as pd


REQUIRED_COLUMNS_ALIASES = {
    "url": ["url", "link", "address", "địa chỉ", "đường dẫn"],
    "keywords": ["keywords", "keyword", "top keywords", "top keyword", "từ khóa", "tu khoa"],
    "traffic": [
        "organic traffic",
        "traffic",
        "organic_traffic",
        "lượt truy cập",
        "luot truy cap",
        "sessions",
    ],
}


def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Chuẩn hóa tên cột về 3 cột chuẩn: url, keywords, traffic."""
    col_map: dict[str, str] = {}
    lower_cols = {c.lower().strip(): c for c in df.columns}

    for standard, aliases in REQUIRED_COLUMNS_ALIASES.items():
        for alias in aliases:
            if alias in lower_cols:
                col_map[lower_cols[alias]] = standard
                break

    df = df.rename(columns=col_map)
    missing = [s for s in REQUIRED_COLUMNS_ALIASES if s not in df.columns]
    if missing:
        raise ValueError(
            f"Không tìm thấy cột: {missing}. "
            f"Các cột hiện có: {list(df.columns)}"
        )

    df = df[["url", "keywords", "traffic"]].copy()
    df["url"] = df["url"].astype(str).str.strip()
    df["keywords"] = df["keywords"].astype(str).str.strip()
    df["traffic"] = pd.to_numeric(df["traffic"], errors="coerce").fillna(0).astype(int)
    return df


def load_csv(path: str) -> pd.DataFrame:
    chunks = pd.read_csv(path, chunksize=10_000, dtype=str)
    df = pd.concat(chunks, ignore_index=True)
    return _normalize_columns(df)


def load_excel(path: str) -> pd.DataFrame:
    """Dùng openpyxl read_only để tránh load ~1.5GB DOM vào RAM."""
    import openpyxl

    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    ws = wb.active
    rows = ws.values
    headers = [str(h) if h is not None else f"col_{i}" for i, h in enumerate(next(rows))]
    df = pd.DataFrame(rows, columns=headers)
    wb.close()
    return _normalize_columns(df)


def _get_gspread_client():
    """Tạo gspread client từ service account."""
    import gspread

    sa_json = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")
    if not sa_json:
        raise EnvironmentError(
            "Cần set biến môi trường GOOGLE_SERVICE_ACCOUNT_JSON "
            "(đường dẫn file hoặc JSON string)"
        )

    if sa_json.strip().startswith("{"):
        creds_info = json.loads(sa_json)
        return gspread.service_account_from_dict(creds_info)
    else:
        return gspread.service_account(filename=sa_json)


def load_sheets(url: str) -> pd.DataFrame:
    """1 batch API call, không paginate row-by-row."""
    import gspread_dataframe

    client = _get_gspread_client()
    sheet = client.open_by_url(url).sheet1
    df = gspread_dataframe.get_as_dataframe(sheet, evaluate_formulas=False)
    df = df.dropna(how="all")
    return _normalize_columns(df)


def load_data(source: str) -> pd.DataFrame:
    """Entry point duy nhất — tự nhận dạng loại nguồn."""
    if re.match(r"https?://docs\.google\.com/spreadsheets", source):
        return load_sheets(source)

    path = Path(source)
    if not path.exists():
        raise FileNotFoundError(f"Không tìm thấy file: {source}")

    suffix = path.suffix.lower()
    if suffix == ".csv":
        return load_csv(str(path))
    elif suffix in {".xlsx", ".xls", ".xlsm"}:
        return load_excel(str(path))
    else:
        raise ValueError(f"Định dạng file không hỗ trợ: {suffix}. Dùng CSV hoặc Excel.")
