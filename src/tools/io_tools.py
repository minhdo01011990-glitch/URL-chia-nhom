"""MCP tools: load_data, export_to_excel."""

from __future__ import annotations

from pathlib import Path

from src.core import data_loader, progress_tracker


def load_data(source: str, session_id: str | None = None) -> dict:
    """
    Đọc dữ liệu từ CSV/Excel/Google Sheets.
    Tạo session mới nếu không truyền session_id.
    Trả về summary (không trả về raw data).
    """
    if session_id is None:
        session_id = progress_tracker.new_session()

    df = data_loader.load_data(source)

    # Lưu checkpoint
    progress_tracker.save_dataframe(session_id, df, "raw")
    progress_tracker.save_progress(
        session_id,
        status="data_loaded",
        source=source,
        total_rows=len(df),
    )

    # Trả về chỉ summary — không trả raw data
    sample = df.head(5)[["url", "traffic"]].to_dict(orient="records")

    return {
        "session_id": session_id,
        "total_rows": len(df),
        "columns": list(df.columns),
        "sample": sample,
        "traffic_sum": int(df["traffic"].sum()),
        "traffic_avg": round(df["traffic"].mean(), 1),
    }


def export_to_excel(session_id: str, output_path: str = "./labeled_output.xlsx") -> dict:
    """Xuất kết quả cuối cùng ra Excel."""
    df = progress_tracker.load_dataframe(session_id, "final")

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    with __import__("pandas").ExcelWriter(str(out), engine="openpyxl") as writer:
        df.to_excel(writer, index=False)

    progress_tracker.save_progress(session_id, status="exported", output_path=str(out))

    return {
        "session_id": session_id,
        "output_path": str(out.resolve()),
        "total_rows": len(df),
        "file_size_kb": round(out.stat().st_size / 1024, 1),
    }
