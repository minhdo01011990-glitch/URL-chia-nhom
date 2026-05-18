"""MCP tools: get_label_distribution, get_low_confidence_samples, apply_corrections."""

from __future__ import annotations

from src.core import progress_tracker


def get_label_distribution(session_id: str) -> dict:
    """Trả về bảng thống kê nhãn — không trả raw data."""
    df = progress_tracker.load_dataframe(session_id, "final")

    total = len(df)
    dist = (
        df.groupby("label")
        .agg(
            count=("url", "count"),
            avg_traffic=("traffic", "mean"),
        )
        .reset_index()
        .sort_values("count", ascending=False)
    )

    rows = []
    for _, row in dist.iterrows():
        rows.append({
            "label": row["label"],
            "count": int(row["count"]),
            "pct": round(row["count"] / total * 100, 1),
            "avg_traffic": round(row["avg_traffic"], 0),
        })

    return {
        "session_id": session_id,
        "total_rows": total,
        "label_count": len(rows),
        "distribution": rows,
    }


def get_low_confidence_samples(
    session_id: str,
    threshold: float = 0.60,
    max_rows: int = 50,
) -> dict:
    """Trả về tối đa 50 hàng có confidence thấp để người dùng review."""
    df = progress_tracker.load_dataframe(session_id, "final")

    low = df[df["confidence"] < threshold].copy()
    low = low.sort_values("confidence").head(max_rows)

    samples = []
    for i, (idx, row) in enumerate(low.iterrows()):
        samples.append({
            "index": i + 1,
            "row_id": int(idx),
            "url": str(row["url"]),
            "current_label": str(row["label"]),
            "confidence": round(float(row["confidence"]), 2),
            "traffic": int(row["traffic"]),
        })

    return {
        "session_id": session_id,
        "total_low_confidence": len(df[df["confidence"] < threshold]),
        "shown": len(samples),
        "threshold": threshold,
        "samples": samples,
    }


def apply_corrections(
    session_id: str,
    corrections: list[dict],
) -> dict:
    """
    Áp dụng chỉnh sửa nhãn thủ công.
    corrections: [{"row_id": 42, "label": "Blog - Kiến thức"}, ...]
    """
    df = progress_tracker.load_dataframe(session_id, "final")

    applied = 0
    skipped = 0
    for corr in corrections:
        row_id = corr.get("row_id")
        new_label = corr.get("label", "").strip()

        if row_id is None or not new_label:
            skipped += 1
            continue

        if row_id in df.index:
            df.loc[row_id, "label"] = new_label
            df.loc[row_id, "method"] = "manual"
            df.loc[row_id, "confidence"] = 1.0
            applied += 1
        else:
            skipped += 1

    if applied > 0:
        progress_tracker.save_dataframe(session_id, df, "final")
        progress_tracker.save_progress(session_id, status="corrections_applied")

    return {
        "session_id": session_id,
        "applied": applied,
        "skipped": skipped,
        "message": f"Đã cập nhật {applied} hàng.",
    }
