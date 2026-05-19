"""Xây dựng label taxonomy từ URL patterns + seed labels của người dùng."""

from __future__ import annotations

import os
import re
import unicodedata
import urllib.request
from collections import Counter, defaultdict
from typing import Optional

import pandas as pd


def _compute_max_labels(analysis_goal: str) -> int:
    """
    Tính số nhãn tối đa phù hợp với mục đích phân tích của người dùng.
    Không cố định ở 20 — điều chỉnh theo mục đích thực tế.
    """
    goal = analysis_goal.lower() if analysis_goal else ""

    # Phân tích traffic tổng quan → ít nhãn, nhóm rộng
    if any(kw in goal for kw in ["tổng quan", "tong quan", "a)", "5-10", "overview"]):
        return 10

    # Landing pages / quảng cáo → chi tiết hơn
    if any(kw in goal for kw in ["trang đích", "trang dich", "landing", "quảng cáo", "quang cao", "b)", "15-25"]):
        return 25

    # Cấu trúc nội dung / danh mục sản phẩm
    if any(kw in goal for kw in ["cấu trúc", "cau truc", "danh mục", "danh muc", "sản phẩm", "san pham", "c)", "10-20"]):
        return 20

    # Mặc định — đủ để phân loại tốt mà không quá chi tiết
    return 15


def _extract_domain(df: "pd.DataFrame") -> Optional[str]:
    """Lấy domain từ URL đầu tiên hợp lệ trong DataFrame."""
    for url in df["url"].dropna().head(10):
        m = re.match(r"^https?://([^/]+)", str(url).strip())
        if m:
            return m.group(1)
    return None


def _fetch_sitemap_urls(domain: str, sample_limit: int = 100) -> list[str]:
    """
    Thử fetch sitemap.xml để lấy thêm URL mẫu đại diện cho cấu trúc website.
    Không bắt buộc — nếu không có sitemap hoặc timeout thì bỏ qua.
    """
    candidates = [
        f"https://{domain}/sitemap.xml",
        f"https://{domain}/sitemap_index.xml",
        f"https://www.{domain}/sitemap.xml",
    ]
    for url in candidates:
        try:
            req = urllib.request.Request(
                url, headers={"User-Agent": "Mozilla/5.0 (compatible; url-labeler/1.0)"}
            )
            with urllib.request.urlopen(req, timeout=5) as r:
                content = r.read(512_000).decode("utf-8", errors="ignore")  # tối đa 512KB
            urls = re.findall(r"<loc>(https?://[^<\s]+)</loc>", content)
            if urls:
                return urls[:sample_limit]
        except Exception:
            continue
    return []


def _normalize_vn(text: str) -> str:
    """Strip Vietnamese diacritics (kể cả đ/ơ/ư) để so sánh fuzzy."""
    text = unicodedata.normalize("NFD", text)
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    # Các ký tự Việt không decompose qua NFD: đ→d, ơ→o, ư→u
    text = text.replace("đ", "d").replace("Đ", "d")
    text = text.replace("ơ", "o").replace("Ơ", "o")
    text = text.replace("ư", "u").replace("Ư", "u")
    return text.lower().replace("-", " ").replace("_", " ").strip()


def _extract_path_signature(url: str) -> str:
    """Chuẩn hóa URL thành template: /category/{slug}/ → /category/{slug}/"""
    url = url.strip().lower()
    # Bỏ scheme + domain
    url = re.sub(r"^https?://[^/]+", "", url)
    # Bỏ query string và fragment
    url = re.sub(r"[?#].*$", "", url)
    # Chuẩn hóa trailing slash
    url = url.rstrip("/") + "/"
    if not url:
        url = "/"

    parts = [p for p in url.split("/") if p]
    if not parts:
        return "/"

    # Segment đầu giữ nguyên (thường là category)
    # Segment 2+: luôn generalize thành {slug} để pattern match mọi trang con
    normalized = []
    for i, part in enumerate(parts):
        if i == 0:
            normalized.append(part)
        else:
            normalized.append("{slug}")

    return "/" + "/".join(normalized) + "/"


def _slug_to_label_name(slug: str) -> str:
    """Chuyển URL slug thành tên nhãn đẹp."""
    slug = slug.replace("-", " ").replace("_", " ")
    return slug.title()


def _infer_label_structure(seed_labels: list[str]) -> str:
    """
    Phát hiện cấu trúc tên nhãn từ seed labels.
    Trả về 'hierarchy' (có dấu ' - ') hoặc 'flat'.
    """
    separator_count = sum(1 for s in seed_labels if " - " in s or "/" in s)
    return "hierarchy" if separator_count >= len(seed_labels) / 2 else "flat"


def _match_seed(segment: str, seed_labels: list[str]) -> Optional[str]:
    """Tìm seed label khớp tốt nhất với một URL segment (normalize dấu tiếng Việt)."""
    seg_norm = _normalize_vn(segment)

    for seed in seed_labels:
        seed_norm = _normalize_vn(seed)
        # Loại bỏ prefix như "danh muc - " để so sánh phần cuối
        seed_core = re.sub(r"^[^ ]+ - ", "", seed_norm).strip()
        if seg_norm == seed_core or seg_norm in seed_core or seed_core in seg_norm:
            return seed
    return None


def _build_clusters(sample_df: pd.DataFrame) -> dict[str, dict]:
    """Group URLs theo signature path, thu thập keyword strings per cluster."""
    clusters: dict[str, dict] = defaultdict(lambda: {"urls": [], "keyword_strings": []})
    has_kw = "keywords" in sample_df.columns
    for _, row in sample_df.iterrows():
        sig = _extract_path_signature(str(row["url"]))
        clusters[sig]["urls"].append(str(row["url"]))
        if has_kw:
            kw = row.get("keywords", "")
            if pd.notna(kw) and str(kw).strip() not in ("", "nan"):
                clusters[sig]["keyword_strings"].append(str(kw).strip())
    return {sig: dict(d) for sig, d in clusters.items()}


def _estimate_cluster_count(sig: str, total_rows: int, cluster_sample_count: int, sample_size: int) -> int:
    ratio = cluster_sample_count / sample_size
    return max(1, int(ratio * total_rows))


_STOPWORDS = {
    "va", "hoac", "cua", "cho", "trong", "tai", "la", "co", "de", "ban",
    "the", "and", "or", "for", "in", "of", "to", "a", "an", "with", "giá",
    "gia", "re", "tot", "chinh", "hang", "chat", "luong", "mua", "ngay",
}


def _extract_top_keywords(keyword_strings: list[str], top_n: int = 5) -> list[str]:
    """Trích top N terms phổ biến nhất từ keyword strings của một cluster.
    Trả về dạng gốc (có dấu tiếng Việt) để hiển thị đẹp; đếm theo dạng normalize.
    """
    # (original_form, normalized_form)
    term_pairs: list[tuple[str, str]] = []
    for kw_str in keyword_strings:
        for segment in re.split(r"[,\n|]+", kw_str):
            original = segment.strip()
            normed = _normalize_vn(original)
            if len(normed) >= 3 and normed not in _STOPWORDS:
                term_pairs.append((original, normed))
    if not term_pairs:
        return []
    # Đếm theo normalized, giữ original đầu tiên gặp cho mỗi norm
    norm_to_original: dict[str, str] = {}
    norm_counter: Counter = Counter()
    for original, normed in term_pairs:
        if normed not in norm_to_original:
            norm_to_original[normed] = original
        norm_counter[normed] += 1
    top_norms = [n for n, _ in norm_counter.most_common(top_n)]
    return [norm_to_original[n] for n in top_norms]


def _match_seed_by_keywords(top_keywords: list[str], seed_labels: list[str]) -> Optional[str]:
    """Fallback: khớp seed label dựa trên top keywords khi URL segment không match."""
    for kw in top_keywords:
        kw_norm = _normalize_vn(kw)
        for seed in seed_labels:
            seed_norm = _normalize_vn(seed)
            seed_core = re.sub(r"^[^ ]+ - ", "", seed_norm).strip()
            # Chỉ match khi seed_core đủ dài để tránh false positive
            if len(seed_core) >= 4 and (kw_norm == seed_core or seed_core in kw_norm):
                return seed
    return None


def build_label_taxonomy(
    df: pd.DataFrame,
    seed_labels: list[str],
    website_description: str = "",
    analysis_goal: str = "",
    sample_size: int = 500,
    use_claude_api: bool = False,
    fetch_sitemap: bool = True,
) -> dict:
    """
    Xây danh sách nhãn gợi ý từ URL patterns + seed labels.

    Trả về dict:
    {
      "labels": [
        {
          "name": "Trang chủ",
          "patterns": [r"^https?://[^/]+/?$"],
          "example_urls": ["https://example.com/"],
          "estimated_count": 1,
          "source": "seed"  # hoặc "inferred" hoặc "claude"
        },
        ...
      ],
      "structure": "hierarchy",  # hoặc "flat"
      "seed_labels": [...],
    }
    """
    total_rows = len(df)
    sample_df = df.sample(min(sample_size, total_rows), random_state=42)

    # Phase 1: Cluster URLs theo signature, thu thập keywords từ sample
    clusters = _build_clusters(sample_df)

    # Bổ sung URL từ sitemap để phát hiện patterns ít gặp trong sample ngẫu nhiên
    if fetch_sitemap:
        domain = _extract_domain(sample_df)
        if domain:
            sitemap_urls = _fetch_sitemap_urls(domain, sample_limit=100)
            for url in sitemap_urls:
                sig = _extract_path_signature(url)
                if sig not in clusters:
                    # Chỉ thêm signature mới — không đếm vào estimated_count
                    clusters[sig] = {"urls": [url], "keyword_strings": [], "_sitemap_only": True}

    # Số nhãn tối đa dựa theo mục đích phân tích — không hard-code ở 20
    MAX_TOTAL_LABELS = _compute_max_labels(analysis_goal)

    # Phase 2: Match clusters với seed labels
    structure = _infer_label_structure(seed_labels)
    label_entries: list[dict] = []
    matched_seeds = set()
    unmatched_clusters: dict[str, dict] = {}

    # Sắp xếp cluster theo số lượng URL (nhiều nhất trước)
    sorted_clusters = sorted(clusters.items(), key=lambda x: len(x[1]["urls"]), reverse=True)

    for sig, cluster_data in sorted_clusters:
        example_urls = cluster_data["urls"]
        top_keywords = _extract_top_keywords(cluster_data["keyword_strings"])
        parts = [p for p in sig.split("/") if p and p != "{slug}"]

        if not parts:
            # Trang chủ
            home_seed = next((s for s in seed_labels if "chủ" in s.lower() or "home" in s.lower()), None)
            label_name = home_seed or "Trang chủ"
            matched_seeds.add(label_name)
            pattern = r"^https?://[^/]+/?$"
        else:
            first_seg = parts[0]
            # Thử match qua URL segment trước
            matched_seed = _match_seed(first_seg, seed_labels)
            # Fallback: match qua top keywords nếu URL segment không khớp
            if matched_seed is None and top_keywords:
                matched_seed = _match_seed_by_keywords(top_keywords, seed_labels)

            if matched_seed:
                label_name = matched_seed
                matched_seeds.add(matched_seed)
                pattern = _sig_to_pattern(sig)
            else:
                unmatched_clusters[sig] = cluster_data
                continue

        estimated = _estimate_cluster_count(sig, total_rows, len(example_urls), len(sample_df))
        label_entries.append({
            "name": label_name,
            "patterns": [pattern],
            "example_urls": example_urls[:3],
            "top_keywords": top_keywords[:3],
            "estimated_count": estimated,
            "confidence": 0.90,
            "source": "seed",
        })

    # Thêm seed labels chưa được match (các nhãn người dùng khai báo nhưng không có URL mẫu)
    for seed in seed_labels:
        if seed not in matched_seeds:
            label_entries.append({
                "name": seed,
                "patterns": [],
                "example_urls": [],
                "top_keywords": [],
                "estimated_count": 0,
                "confidence": 0.80,
                "source": "seed_no_match",
            })

    # Phase 3: Infer nhãn mới cho clusters chưa match — group theo first path segment
    # (KHÔNG tạo 1 label per signature — tránh bùng nổ 400+ labels cho site lớn)
    current_label_count = len({e["name"] for e in label_entries})
    remaining_slots = max(0, MAX_TOTAL_LABELS - current_label_count)

    if remaining_slots > 0 and unmatched_clusters:
        # Gộp tất cả clusters theo first path segment
        seg_groups: dict[str, dict] = defaultdict(
            lambda: {"urls": [], "keyword_strings": [], "estimated_count": 0, "sigs": []}
        )
        for sig, cluster_data in unmatched_clusters.items():
            parts = [p for p in sig.split("/") if p and p != "{slug}"]
            if not parts:
                continue
            first_seg = parts[0]
            seg_groups[first_seg]["urls"].extend(cluster_data["urls"][:2])
            seg_groups[first_seg]["keyword_strings"].extend(cluster_data["keyword_strings"])
            seg_groups[first_seg]["sigs"].append(sig)
            # Cluster từ sitemap không có đủ count để ước tính — bỏ qua estimated_count
            if not cluster_data.get("_sitemap_only"):
                seg_groups[first_seg]["estimated_count"] += _estimate_cluster_count(
                    sig, total_rows, len(cluster_data["urls"]), len(sample_df)
                )

        # Sort theo estimated_count DESC, giữ top remaining_slots nhóm
        sorted_groups = sorted(
            seg_groups.items(),
            key=lambda x: x[1]["estimated_count"],
            reverse=True,
        )[:remaining_slots]

        for first_seg, data in sorted_groups:
            top_keywords = _extract_top_keywords(data["keyword_strings"])
            inferred_name = _infer_label_name([first_seg], structure, seed_labels, top_keywords)
            # Pattern bao phủ tất cả URLs bắt đầu bằng /first_seg/
            pattern = rf"/{re.escape(first_seg)}/"
            label_entries.append({
                "name": inferred_name,
                "patterns": [pattern],
                "example_urls": data["urls"][:3],
                "top_keywords": top_keywords[:3],
                "estimated_count": data["estimated_count"],
                "confidence": 0.75,
                "source": "inferred",
            })

    # Phase 4 (optional): Gọi Claude API cho clusters mơ hồ
    if use_claude_api and os.environ.get("ANTHROPIC_API_KEY"):
        ambiguous = [e for e in label_entries if e["confidence"] < 0.80 and e["example_urls"]]
        if ambiguous:
            label_entries = _enrich_with_claude(label_entries, seed_labels, website_description)

    # Dedup — merge patterns/keywords của các entry cùng tên (giữ thứ tự xuất hiện đầu tiên)
    merged: dict[str, dict] = {}
    for entry in label_entries:
        name = entry["name"]
        if name not in merged:
            merged[name] = entry
        else:
            # Gộp patterns
            existing_pats = set(merged[name].get("patterns", []))
            for p in entry.get("patterns", []):
                if p not in existing_pats:
                    merged[name].setdefault("patterns", []).append(p)
                    existing_pats.add(p)
            # Gộp top_keywords (unique, giữ tối đa 5)
            existing_kws = set(merged[name].get("top_keywords", []))
            for kw in entry.get("top_keywords", []):
                if kw not in existing_kws and len(merged[name]["top_keywords"]) < 5:
                    merged[name]["top_keywords"].append(kw)
                    existing_kws.add(kw)
            merged[name]["estimated_count"] += entry["estimated_count"]
            if not merged[name]["example_urls"] and entry["example_urls"]:
                merged[name]["example_urls"] = entry["example_urls"]

    deduped = list(merged.values())

    # Sắp xếp: seed trước, inferred sau, theo estimated_count DESC
    deduped.sort(key=lambda e: (e["source"] not in ("seed", "seed_no_match"), -e["estimated_count"]))

    # Hard cap theo mục đích phân tích — seed labels luôn được giữ
    if len(deduped) > MAX_TOTAL_LABELS:
        seed_entries = [e for e in deduped if e["source"] in ("seed", "seed_no_match")]
        inferred_entries = [e for e in deduped if e["source"] not in ("seed", "seed_no_match")]
        max_inferred = max(0, MAX_TOTAL_LABELS - len(seed_entries))
        deduped = seed_entries + inferred_entries[:max_inferred]

    return {
        "labels": deduped,
        "structure": structure,
        "seed_labels": seed_labels,
        "total_rows": total_rows,
        "sample_size": len(sample_df),
        "max_labels_target": MAX_TOTAL_LABELS,
    }


def _sig_to_pattern(sig: str) -> str:
    """Chuyển URL signature thành regex pattern."""
    parts = [p for p in sig.split("/") if p]
    if not parts:
        return r"^https?://[^/]+/?$"

    pat_parts = []
    for part in parts:
        if part == "{slug}":
            pat_parts.append(r"[^/]+")
        else:
            # Escape đặc biệt cho regex
            pat_parts.append(re.escape(part))

    inner = "/".join(pat_parts)
    return rf"/{inner}/?"


def _infer_label_name(
    parts: list[str],
    structure: str,
    seed_labels: list[str],
    top_keywords: list[str] | None = None,
) -> str:
    """Suy ra tên nhãn mới theo cùng cấu trúc với seed labels."""
    main_seg = parts[0]

    # Ưu tiên keyword làm display name: tiếng Việt có dấu, sát nghĩa hơn ASCII slug.
    # Lấy 2 từ đầu của keyword ngắn nhất để tránh tên nhãn quá dài.
    if top_keywords:
        best_kw = min(top_keywords, key=len)
        words = best_kw.split()
        # Lấy 2 từ đầu nếu keyword dài hơn 2 từ, còn ngắn thì giữ nguyên
        display = " ".join(words[:2]).title() if len(words) > 2 else best_kw.title()
    else:
        display = _slug_to_label_name(main_seg)

    if structure == "hierarchy":
        # Tìm prefix phù hợp từ seed labels có dạng "X - Y"
        seed_prefixes = [s.split(" - ")[0] for s in seed_labels if " - " in s]
        if seed_prefixes and len(parts) > 1:
            prefix = seed_prefixes[0]
            return f"{prefix} - {display}"
        # Single-segment nhưng structure hierarchy: giữ tên phẳng (không biết prefix)
    return display


def _enrich_with_claude(
    label_entries: list[dict],
    seed_labels: list[str],
    website_description: str,
) -> list[dict]:
    """Gọi 1 Claude API call để cải thiện nhãn mơ hồ."""
    try:
        import anthropic
        client = anthropic.Anthropic()

        seed_examples = "\n".join(f"- {s}" for s in seed_labels[:10])
        ambiguous_items: list[str] = []
        for entry in label_entries:
            if entry["confidence"] < 0.80 and entry["example_urls"]:
                for url in entry["example_urls"][:2]:
                    kws = entry.get("top_keywords", [])
                    kw_hint = f" [keywords: {', '.join(kws[:3])}]" if kws else ""
                    ambiguous_items.append(f"{url}{kw_hint}")

        if not ambiguous_items:
            return label_entries

        prompt = f"""Website: {website_description}

Nhãn mẫu (dùng làm khuôn mẫu đặt tên):
{seed_examples}

Các URL chưa được phân loại (kèm top keywords của trang):
{chr(10).join(ambiguous_items[:20])}

Gợi ý nhãn cho mỗi URL theo ĐÚNG cấu trúc tên của nhãn mẫu trên.
Trả về dạng JSON: [{{"url": "...", "label": "..."}}]"""

        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=500,
            messages=[{"role": "user", "content": prompt}],
        )

        import json
        text = response.content[0].text.strip()
        # Extract JSON từ response
        json_match = re.search(r"\[.*\]", text, re.DOTALL)
        if json_match:
            suggestions = json.loads(json_match.group())
            url_to_label = {s["url"]: s["label"] for s in suggestions}

            for entry in label_entries:
                if entry["confidence"] < 0.80:
                    for url in entry["example_urls"][:2]:
                        if url in url_to_label:
                            entry["name"] = url_to_label[url]
                            entry["source"] = "claude"
                            entry["confidence"] = 0.85
                            break
    except Exception:
        pass  # Claude API không bắt buộc — tiếp tục với kết quả hiện có

    return label_entries
