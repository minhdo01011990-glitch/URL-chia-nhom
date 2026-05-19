"""MCP tools: build_label_taxonomy, save_label_config, apply_rule_based_labels."""

from __future__ import annotations

from src.core import classifier, progress_tracker, taxonomy_builder


def build_label_taxonomy(
    session_id: str,
    seed_labels: list[str],
    website_description: str = "",
    analysis_goal: str = "",
    use_claude_api: bool = False,
) -> dict:
    """
    Phase 1: Xây danh sách nhãn gợi ý từ URL patterns + seed labels.
    Trả về taxonomy để người dùng review — không lưu tự động.
    """
    df = progress_tracker.load_dataframe(session_id, "raw")

    taxonomy = taxonomy_builder.build_label_taxonomy(
        df=df,
        seed_labels=seed_labels,
        website_description=website_description,
        analysis_goal=analysis_goal,
        use_claude_api=use_claude_api,
    )

    # Lưu full taxonomy (có patterns) để save_label_config dùng lại
    progress_tracker.save_label_config(session_id, {"labels": taxonomy["labels"], "_draft": True})
    progress_tracker.save_progress(session_id, status="taxonomy_built")

    # Format trả về Claude — compact để tiết kiệm token
    # Truncate để đảm bảo response không vượt MCP token limit (~3,000 chars)
    MAX_LABELS_IN_RESPONSE = 20
    labels_to_show = taxonomy["labels"][:MAX_LABELS_IN_RESPONSE]

    label_summary = [
        {
            "index": i + 1,
            "name": e["name"],
            # Truncate URL dài để tiết kiệm token
            "example_url": (e["example_urls"][0][:100] if e["example_urls"] else ""),
            "top_keywords": [kw[:30] for kw in e.get("top_keywords", [])[:3]],
            "estimated_count": e["estimated_count"],
            "source": e["source"],
        }
        for i, e in enumerate(labels_to_show)
    ]

    return {
        "session_id": session_id,
        "label_count": len(taxonomy["labels"]),
        "labels": label_summary,
        "structure": taxonomy["structure"],
        "total_rows": taxonomy["total_rows"],
    }


def save_label_config(
    session_id: str,
    labels: list[dict] | None = None,
) -> dict:
    """
    Lưu taxonomy đã được người dùng confirm.
    labels: danh sách đã chỉnh sửa (nếu None, dùng taxonomy built trước đó).
    """
    # Nếu không có labels mới, phải build lại từ raw — không hỗ trợ lưu khi không có data
    if labels is None:
        raise ValueError("Cần truyền labels đã confirm từ build_label_taxonomy")

    # Load draft taxonomy để lấy merged patterns (nếu có)
    draft_patterns: dict[str, list[str]] = {}
    try:
        draft = progress_tracker.load_label_config(session_id)
        for e in draft.get("labels", []):
            if e.get("patterns"):
                draft_patterns[e["name"]] = e["patterns"]
    except Exception:
        pass

    # Bổ sung patterns từ draft hoặc tự generate từ example_url
    enriched = []
    for entry in labels:
        if not entry.get("patterns"):
            if entry["name"] in draft_patterns:
                entry["patterns"] = draft_patterns[entry["name"]]
            elif entry.get("example_url"):
                sig = taxonomy_builder._extract_path_signature(entry["example_url"])
                entry["patterns"] = [taxonomy_builder._sig_to_pattern(sig)]
        enriched.append(entry)

    taxonomy = {"labels": enriched}
    path = progress_tracker.save_label_config(session_id, taxonomy)
    progress_tracker.save_progress(session_id, status="label_config_saved", label_count=len(enriched))

    return {
        "session_id": session_id,
        "saved_path": str(path),
        "label_count": len(enriched),
    }


def apply_rule_based_labels(session_id: str, use_default_fallbacks: bool = False) -> dict:
    """
    Phase 2a: Classify toàn bộ data bằng regex rules.
    Lưu checkpoint rule_results.parquet.
    Trả về số lượng đã label và chưa label.
    use_default_fallbacks=False (mặc định): bỏ qua broad fallback rules (Danh mục/Sản phẩm mặc định)
      để các URL mơ hồ được gửi lên Claude Batch API thay vì bị gán nhãn sai.
    use_default_fallbacks=True: dùng generic fallbacks — chỉ dùng khi KHÔNG có Claude API key.
    """
    df = progress_tracker.load_dataframe(session_id, "raw")
    label_config = progress_tracker.load_label_config(session_id)

    clf = classifier.build_classifier(label_config=label_config, use_default_fallbacks=use_default_fallbacks)
    df = clf.classify(df)

    # Validate: chỉ giữ labels nằm trong danh sách đã confirm — tránh sinh nhãn ngoài ý muốn
    valid_label_names = {e["name"] for e in label_config.get("labels", [])} if label_config else set()
    if valid_label_names:
        invalid_mask = df["label"].notna() & ~df["label"].isin(valid_label_names)
        n_invalid = int(invalid_mask.sum())
        if n_invalid > 0:
            df.loc[invalid_mask, "label"] = None
            df.loc[invalid_mask, "confidence"] = 0.0
            df.loc[invalid_mask, "method"] = None
    else:
        n_invalid = 0

    # Lưu kết quả
    progress_tracker.save_dataframe(session_id, df, "rule_results")
    progress_tracker.save_progress(session_id, status="rule_labeled")

    labeled = df["label"].notna().sum()
    unlabeled = df["label"].isna().sum()
    coverage = round(labeled / len(df) * 100, 1)

    # Phân phối nhãn (compact)
    dist = df["label"].value_counts().head(15).to_dict()

    # Phát hiện mất cân bằng: nhãn nào chiếm > 50% tổng rows sau rule-based
    dominant_label = None
    dominant_pct = None
    imbalanced = False
    if dist and labeled > 0:
        top_label, top_count = max(dist.items(), key=lambda x: x[1])
        top_pct = round(top_count / len(df) * 100, 1)
        if top_pct > 50:
            imbalanced = True
            dominant_label = top_label
            dominant_pct = top_pct

    return {
        "session_id": session_id,
        "total_rows": len(df),
        "labeled": int(labeled),
        "unlabeled": int(unlabeled),
        "coverage_pct": coverage,
        "label_distribution": {str(k): int(v) for k, v in dist.items()},
        "labels_outside_confirmed_list": n_invalid,
        "imbalanced": imbalanced,
        "dominant_label": dominant_label,
        "dominant_pct": dominant_pct,
    }
