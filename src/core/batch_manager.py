"""Claude Batch API orchestration — submit, poll, merge."""

from __future__ import annotations

import math
import re
import time
from typing import Iterator

import pandas as pd


BATCH_MAX_SIZE = 10_000
HAIKU_MODEL = "claude-haiku-4-5-20251001"


def _build_system_content(valid_labels: list[str]) -> list[dict]:
    """
    System prompt với prompt caching — dùng chung cho toàn batch.
    Model trả về index (số) thay vì tên nhãn để tiết kiệm output tokens ~8x.
    """
    labels_indexed = "\n".join(f"{i}: {lbl}" for i, lbl in enumerate(valid_labels))
    return [
        {
            "type": "text",
            "text": (
                "Phân loại URL website. Trả lời CHỈ với số thứ tự (index) của nhãn phù hợp nhất.\n\n"
                f"Nhãn hợp lệ:\n{labels_indexed}\n\n"
                "Input: đường dẫn URL | keywords\n"
                "Output: chỉ số thứ tự (ví dụ: 3)"
            ),
            "cache_control": {"type": "ephemeral"},
        }
    ]


def _build_batch_request(row: pd.Series, system_content: list[dict]) -> dict:
    """
    Compact request:
    - URL: chỉ path (bỏ scheme + domain) — ~20 tokens thay vì ~60
    - Keywords: tối đa 60 chars — ~15 tokens
    - max_tokens: 10 (chỉ cần 1-2 chữ số index)
    """
    url = str(row["url"])
    path = re.sub(r"^https?://[^/]+", "", url).strip() or "/"
    if len(path) > 150:
        path = path[:150]

    keywords = str(row.get("keywords", "")).strip()[:60]
    content = f"{path} | {keywords}" if keywords else path

    return {
        "custom_id": str(row.name),
        "params": {
            "model": HAIKU_MODEL,
            "max_tokens": 10,
            "system": system_content,
            "messages": [{"role": "user", "content": content}],
        },
    }


def submit_batch(
    unlabeled_df: pd.DataFrame,
    valid_labels: list[str],
    batch_index: int = 0,
) -> str:
    """
    Gửi một batch (≤ 10,000 rows) lên Claude Batch API.
    System prompt được build một lần và chia sẻ qua toàn batch (prompt caching).
    Trả về batch_id.
    """
    import anthropic

    client = anthropic.Anthropic()
    system_content = _build_system_content(valid_labels)
    requests = [
        _build_batch_request(row, system_content)
        for _, row in unlabeled_df.iterrows()
    ]

    batch = client.beta.messages.batches.create(requests=requests)
    return batch.id


def submit_all_batches(
    unlabeled_df: pd.DataFrame,
    valid_labels: list[str],
) -> list[str]:
    """Chia thành nhiều batches nếu > 10k rows. Trả về list batch_ids."""
    n_batches = math.ceil(len(unlabeled_df) / BATCH_MAX_SIZE)
    chunks = [
        unlabeled_df.iloc[i * BATCH_MAX_SIZE: (i + 1) * BATCH_MAX_SIZE]
        for i in range(n_batches)
    ]

    batch_ids = []
    for i, chunk in enumerate(chunks):
        batch_id = submit_batch(chunk, valid_labels, batch_index=i)
        batch_ids.append(batch_id)

    return batch_ids


def poll_batch(batch_id: str) -> dict:
    """
    Trả về dict với keys: status, request_counts, batch_id.
    status: 'in_progress' | 'ended' | 'error'
    """
    import anthropic

    client = anthropic.Anthropic()
    batch = client.beta.messages.batches.retrieve(batch_id)

    return {
        "batch_id": batch_id,
        "status": batch.processing_status,
        "request_counts": {
            "processing": batch.request_counts.processing,
            "succeeded": batch.request_counts.succeeded,
            "errored": batch.request_counts.errored,
            "canceled": batch.request_counts.canceled,
            "expired": batch.request_counts.expired,
        },
    }


def wait_for_batch(
    batch_id: str,
    poll_interval: int = 60,
    max_wait_seconds: int = 7200,
) -> dict:
    """Polling đơn giản — chờ đến khi batch ended."""
    elapsed = 0
    while elapsed < max_wait_seconds:
        status = poll_batch(batch_id)
        if status["status"] == "ended":
            return status
        time.sleep(poll_interval)
        elapsed += poll_interval
    raise TimeoutError(f"Batch {batch_id} chưa hoàn tất sau {max_wait_seconds}s")


def stream_batch_results(
    batch_id: str,
    valid_labels: list[str],
) -> Iterator[tuple[str, str | None]]:
    """
    Streaming iterator — yield (custom_id, label_or_None).
    Parse index → label name; fallback to direct name match nếu model không tuân thủ.
    """
    import anthropic

    client = anthropic.Anthropic()
    valid_set = set(valid_labels)

    for result in client.beta.messages.batches.results(batch_id):
        custom_id = result.custom_id
        if result.result.type == "succeeded":
            text = result.result.message.content[0].text.strip()
            # Parse index (primary path)
            try:
                idx = int(text)
                label = valid_labels[idx] if 0 <= idx < len(valid_labels) else None
            except (ValueError, IndexError):
                # Fallback: model trả về tên nhãn trực tiếp
                label = text if text in valid_set else None
            yield custom_id, label
        else:
            yield custom_id, None


def merge_batch_results(
    df: pd.DataFrame,
    batch_ids: list[str],
    valid_labels: list[str],
    fallback_label: str = "Khác",
) -> pd.DataFrame:
    """
    Merge kết quả từ tất cả batch vào df.
    Trả về df với cột 'label' và 'method' đã được điền.
    """
    df = df.copy()

    for batch_id in batch_ids:
        for custom_id, label in stream_batch_results(batch_id, valid_labels):
            try:
                idx = int(custom_id)
            except (ValueError, TypeError):
                continue

            if idx not in df.index:
                continue

            if label:
                df.loc[idx, "label"] = label
                df.loc[idx, "method"] = "claude"
                df.loc[idx, "confidence"] = 0.85
            else:
                df.loc[idx, "label"] = fallback_label
                df.loc[idx, "method"] = "claude_fallback"
                df.loc[idx, "confidence"] = 0.50

    return df
