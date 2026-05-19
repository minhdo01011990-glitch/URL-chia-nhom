"""MCP tools: submit_claude_batch, poll_batch_status, merge_batch_results, qa_labeled_data."""

from __future__ import annotations

import json as _json
import re as _re

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
    """Kiểm tra tiến độ tất cả batches của session.
    Tự động phát hiện batch treo (>30 phút mà succeeded=0) và cảnh báo.
    """
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

    # Phát hiện batch treo: đang in_progress nhưng succeeded=0 sau >30 phút
    STUCK_THRESHOLD_SECONDS = 30 * 60  # 30 phút
    stuck_batches = []
    for s in statuses:
        if (
            s["status"] == "in_progress"
            and s["request_counts"]["succeeded"] == 0
            and s.get("elapsed_seconds") is not None
            and s["elapsed_seconds"] > STUCK_THRESHOLD_SECONDS
        ):
            stuck_batches.append(s["batch_id"])

    result = {
        "session_id": session_id,
        "all_ended": all_ended,
        "total_succeeded": total_succeeded,
        "total_processing": total_processing,
        "batches": statuses,
    }

    if stuck_batches:
        elapsed_min = max(
            s.get("elapsed_seconds", 0) for s in statuses
            if s["batch_id"] in stuck_batches
        ) // 60
        result["stuck_batches"] = stuck_batches
        result["warning"] = (
            f"⚠ {len(stuck_batches)} batch treo — đã chạy {elapsed_min}+ phút nhưng succeeded=0. "
            f"Gọi cancel_stale_batches_tool(session_id) để hủy và submit lại."
        )

    return result


def cancel_stale_batches(session_id: str) -> dict:
    """
    Hủy tất cả batches đang in_progress của session (dùng khi batch treo).
    Sau đó có thể submit lại bằng submit_claude_batch_tool.
    """
    progress = progress_tracker.load_progress(session_id)
    if not progress:
        raise ValueError(f"Session {session_id} không tồn tại")

    batch_ids = progress.get("batch_ids", [])
    if not batch_ids:
        return {
            "session_id": session_id,
            "cancelled": [],
            "message": "Không có batch nào để hủy",
        }

    cancelled = []
    errors = []
    for bid in batch_ids:
        result = batch_manager.cancel_batch(bid)
        if result.get("cancelled"):
            cancelled.append(bid)
        else:
            errors.append({"batch_id": bid, "error": result.get("error", "unknown")})

    # Xóa batch_ids cũ khỏi progress để submit lại được
    if cancelled:
        progress_tracker.save_progress(session_id, batch_ids=[], status="batch_cancelled")

    return {
        "session_id": session_id,
        "cancelled": cancelled,
        "errors": errors,
        "message": (
            f"Đã hủy {len(cancelled)} batch. Gọi submit_claude_batch_tool(session_id) để submit lại."
            if cancelled else "Không có batch nào được hủy."
        ),
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


def qa_labeled_data(session_id: str, sample_size: int = 20) -> dict:
    """
    Stratified sampling ngẫu nhiên từ kết quả đã đánh nhãn, gửi Claude Haiku kiểm tra.
    Trả về danh sách URL có nhãn nghi ngờ kèm row_id (dùng với apply_corrections_tool).
    """
    import anthropic

    df = progress_tracker.load_dataframe(session_id, "final")
    label_config = progress_tracker.load_label_config(session_id)
    valid_labels = [e["name"] for e in label_config.get("labels", [])] if label_config else []

    if df.empty or not valid_labels:
        return {
            "session_id": session_id,
            "checked": 0,
            "wrong_count": 0,
            "wrong_items": [],
            "message": "Không có dữ liệu hoặc chưa có label config.",
        }

    # Stratified sampling: lấy đều từ mỗi nhãn
    per_label = max(1, sample_size // max(1, df["label"].nunique()))
    sample = (
        df.groupby("label", group_keys=False)
        .apply(lambda g: g.sample(min(per_label, len(g)), random_state=42))
        .head(sample_size)
    )

    labels_str = "\n".join(f"{i}: {lbl}" for i, lbl in enumerate(valid_labels))

    rows_text = []
    for idx, row in sample.iterrows():
        path = _re.sub(r"^https?://[^/]+", "", str(row["url"])).strip() or "/"
        if len(path) > 120:
            path = path[:120]
        kw = str(row.get("keywords", "")).strip()[:60]
        line = f"[{int(idx)}] {path}"
        if kw and kw not in ("nan", ""):
            line += f" | {kw}"
        line += f" → {row['label']}"
        rows_text.append(line)

    prompt = (
        f"Nhãn hợp lệ (dùng index khi trả lời):\n{labels_str}\n\n"
        "Kiểm tra các nhãn đã gán bên dưới. Với mỗi dòng [row_id], "
        "trả về 'ok' hoặc index nhãn đúng hơn.\n\n"
        + "\n".join(rows_text)
        + '\n\nJSON: [{"row_id": int, "verdict": "ok"} hoặc '
        '{"row_id": int, "verdict": "wrong", "suggested_index": int, "reason": "..."}]'
    )

    try:
        client = anthropic.Anthropic(timeout=30.0)
        resp = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=800,
            messages=[{"role": "user", "content": prompt}],
        )
        text = resp.content[0].text.strip()

        wrong_items = []
        json_match = _re.search(r"\[.*?\]", text, _re.DOTALL)
        if json_match:
            results = _json.loads(json_match.group())
            for item in results:
                if item.get("verdict") == "wrong":
                    row_id = item.get("row_id")
                    suggested_idx = item.get("suggested_index")
                    suggested = (
                        valid_labels[suggested_idx]
                        if (suggested_idx is not None and 0 <= suggested_idx < len(valid_labels))
                        else None
                    )
                    current = str(df.loc[row_id, "label"]) if (row_id is not None and row_id in df.index) else ""
                    url = str(df.loc[row_id, "url"]) if (row_id is not None and row_id in df.index) else ""
                    wrong_items.append({
                        "row_id": row_id,
                        "url": url,
                        "current_label": current,
                        "suggested_label": suggested,
                        "reason": item.get("reason", ""),
                    })

        msg = (
            f"✓ Kiểm tra {len(sample)} URL: tất cả nhãn hợp lý."
            if not wrong_items
            else f"⚠ Kiểm tra {len(sample)} URL: {len(wrong_items)} nhãn có thể sai."
        )
        return {
            "session_id": session_id,
            "checked": len(sample),
            "wrong_count": len(wrong_items),
            "wrong_items": wrong_items,
            "message": msg,
        }

    except Exception as e:
        return {
            "session_id": session_id,
            "checked": 0,
            "wrong_count": 0,
            "wrong_items": [],
            "error": str(e)[:120],
            "message": f"Không thể kiểm tra QA: {str(e)[:120]}",
        }


def force_finalize(session_id: str, fallback_label: str = "Sản phẩm - Khác") -> dict:
    """
    Bỏ qua Batch API — gán nhãn fallback cho các URL còn lại và lưu final.parquet.
    Dùng khi muốn skip batch hoặc batch đang chạy quá lâu.
    """
    progress = progress_tracker.load_progress(session_id)
    if not progress:
        raise ValueError(f"Session {session_id} không tồn tại")

    df = progress_tracker.load_dataframe(session_id, "rule_results")

    unlabeled_mask = df["label"].isna()
    unlabeled_count = int(unlabeled_mask.sum())

    if unlabeled_count > 0:
        df.loc[unlabeled_mask, "label"] = fallback_label
        df.loc[unlabeled_mask, "method"] = "manual_skip"
        df.loc[unlabeled_mask, "confidence"] = 0.50

    progress_tracker.save_dataframe(session_id, df, "final")
    progress_tracker.save_progress(session_id, status="merged")

    rule_count = int((df["method"] == "rule").sum())

    return {
        "session_id": session_id,
        "total_rows": len(df),
        "rule_labeled": rule_count,
        "skipped_labeled": unlabeled_count,
        "fallback_label_used": fallback_label,
        "message": f"Đã bỏ qua batch — {unlabeled_count} URL gán nhãn '{fallback_label}'. final.parquet đã lưu.",
    }
