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
    label_summary = [
        {
            "index": i + 1,
            "name": e["name"],
            "example_url": e["example_urls"][0] if e["example_urls"] else "",
            "top_keywords": e.get("top_keywords", [])[:3],
            "estimated_count": e["estimated_count"],
            "source": e["source"],
        }
        for i, e in enumerate(taxonomy["labels"])
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


def apply_rule_based_labels(session_id: str, use_default_fallbacks: bool = True) -> dict:
    """
    Phase 2a: Classify toàn bộ data bằng regex rules.
    Lưu checkpoint rule_results.parquet.
    Trả về số lượng đã label và chưa label.
    use_default_fallbacks=False: bỏ qua broad fallback rules (Danh mục/Sản phẩm mặc định)
      để các URL này được gửi lên Claude thay vì bị gán nhãn sai.
    """
    df = progress_tracker.load_dataframe(session_id, "raw")
    label_config = progress_tracker.load_label_config(session_id)

    clf = classifier.build_classifier(label_config=label_config, use_default_fallbacks=use_default_fallbacks)
    df = clf.classify(df)

    # Lưu kết quả
    progress_tracker.save_dataframe(session_id, df, "rule_results")
    progress_tracker.save_progress(session_id, status="rule_labeled")

    labeled = df["label"].notna().sum()
    unlabeled = df["label"].isna().sum()
    coverage = round(labeled / len(df) * 100, 1)

    # Phân phối nhãn (compact)
    dist = df["label"].value_counts().head(15).to_dict()

    return {
        "session_id": session_id,
        "total_rows": len(df),
        "labeled": int(labeled),
        "unlabeled": int(unlabeled),
        "coverage_pct": coverage,
        "label_distribution": {str(k): int(v) for k, v in dist.items()},
    }
