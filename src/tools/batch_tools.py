"""MCP tools: submit_claude_batch, poll_batch_status, merge_batch_results."""

from __future__ import annotations

from src.core import batch_manager, progress_tracker


def submit_claude_batch(session_id: str) -> dict:
    """
    Lấy các hàng chưa có nhãn → submit lên Claude Batch API.
    Trả về batch_ids và ước tính chi phí.
    """
    df = progress_tracker.load_dataframe(session_id, "rule_results")
    label_config = progress_tracker.load_label_config(session_id)

    if label_config is None:
        raise ValueError(f"Chưa có label_config cho session {session_id}")

    valid_labels = [e["name"] for e in label_config.get("labels", [])]
    unlabeled_df = df[df["label"].isna()].copy()

    if unlabeled_df.empty:
        progress_tracker.save_progress(session_id, status="batch_skipped", batch_ids=[])
        return {
            "session_id": session_id,
            "unlabeled_count": 0,
            "batch_ids": [],
            "message": "Tất cả hàng đã được label bằng rules — không cần gọi Claude API",
        }

    batch_ids = batch_manager.submit_all_batches(unlabeled_df, valid_labels)

    # Ước tính chi phí với các tối ưu:
    # - System prompt (~100 tokens) cached → cache_read price = 10% of $0.25 = $0.025/1M
    # - User message (~20 tokens: path + keywords) → $0.25/1M
    # - Output (~2 tokens: chỉ số index) → $1.25/1M
    n = len(unlabeled_df)
    est_cost = round(
        (n * 100 / 1_000_000 * 0.025)  # system prompt (cached read)
        + (n * 20 / 1_000_000 * 0.25)  # user message input
        + (n * 2 / 1_000_000 * 1.25),  # output (index digit)
        5,
    )

    progress_tracker.save_progress(
        session_id,
        status="batch_submitted",
        batch_ids=batch_ids,
        unlabeled_count=n,
    )

    return {
        "session_id": session_id,
        "unlabeled_count": n,
        "batch_count": len(batch_ids),
        "batch_ids": batch_ids,
        "estimated_cost_usd": est_cost,
        "message": f"Đã submit {n:,} hàng lên {len(batch_ids)} batch. Thường mất 10-30 phút.",
    }


def poll_batch_status(session_id: str) -> dict:
    """Kiểm tra tiến độ tất cả batches của session."""
    progress = progress_tracker.load_progress(session_id)
    if not progress:
        raise ValueError(f"Session {session_id} không tồn tại")

    batch_ids = progress.get("batch_ids", [])
    if not batch_ids:
        return {
            "session_id": session_id,
            "status": "no_batches",
            "message": "Không có batch nào đang chạy",
        }

    statuses = [batch_manager.poll_batch(bid) for bid in batch_ids]

    all_ended = all(s["status"] == "ended" for s in statuses)
    total_succeeded = sum(s["request_counts"]["succeeded"] for s in statuses)
    total_processing = sum(s["request_counts"]["processing"] for s in statuses)

    if all_ended:
        progress_tracker.save_progress(session_id, status="batch_ended")

    return {
        "session_id": session_id,
        "all_ended": all_ended,
        "total_succeeded": total_succeeded,
        "total_processing": total_processing,
        "batches": statuses,
    }


def merge_batch_results(session_id: str) -> dict:
    """
    Ghép kết quả Claude batch vào rule_results.
    Lưu final.parquet.
    """
    progress = progress_tracker.load_progress(session_id)
    if not progress:
        raise ValueError(f"Session {session_id} không tồn tại")

    df = progress_tracker.load_dataframe(session_id, "rule_results")
    label_config = progress_tracker.load_label_config(session_id)
    valid_labels = [e["name"] for e in label_config.get("labels", [])]
    batch_ids = progress.get("batch_ids", [])

    if batch_ids:
        df = batch_manager.merge_batch_results(df, batch_ids, valid_labels)

    # Fallback: hàng vẫn chưa có nhãn → gán "Khác"
    still_unlabeled = df["label"].isna().sum()
    if still_unlabeled > 0:
        df.loc[df["label"].isna(), "label"] = "Khác"
        df.loc[df["method"].isna(), "method"] = "fallback"
        df.loc[df["confidence"] == 0.0, "confidence"] = 0.30

    progress_tracker.save_dataframe(session_id, df, "final")
    progress_tracker.save_progress(session_id, status="merged")

    rule_count = (df["method"] == "rule").sum()
    claude_count = (df["method"] == "claude").sum()
    fallback_count = (df["method"].isin(["claude_fallback", "fallback"])).sum()

    return {
        "session_id": session_id,
        "total_rows": len(df),
        "rule_labeled": int(rule_count),
        "claude_labeled": int(claude_count),
        "fallback_labeled": int(fallback_count),
    }
