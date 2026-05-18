"""Rule-based URL classifier — vectorized pandas, không dùng df.apply()."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

import pandas as pd


@dataclass
class Rule:
    pattern: str
    label: str
    confidence: float
    priority: int = 50  # số nhỏ hơn = ưu tiên cao hơn
    flags: int = re.IGNORECASE

    def __post_init__(self):
        re.compile(self.pattern, self.flags)  # validate pattern sớm


# Các rule mặc định — sorted theo priority ASC trong build_classifier()
DEFAULT_RULES: list[Rule] = [
    # Trang chủ
    Rule(r"^https?://[^/]+/?$", "Trang chủ", 1.0, priority=1),
    Rule(r"^https?://[^/]+/(?:index\.html?|trang-chu|home)/?$", "Trang chủ", 0.98, priority=2),
    # Trang giao dịch
    Rule(r"/(?:cart|gio-hang|checkout|thanh-toan|payment|order|don-hang)", "Trang giao dịch", 0.99, priority=5),
    # Tìm kiếm
    Rule(r"/(?:search|tim-kiem|tim_kiem)\b", "Trang tìm kiếm", 0.98, priority=6),
    # Tài khoản
    Rule(r"/(?:account|tai-khoan|login|dang-nhap|register|dang-ky|logout)", "Trang tài khoản", 0.97, priority=7),
    # Blog / tin tức / kiến thức
    Rule(r"/(?:blog|tin-tuc|tin_tuc|news|kien-thuc|kien_thuc|bai-viet|huong-dan)/", "Blog", 0.95, priority=10),
    # Trang khuyến mãi / deal
    Rule(r"/(?:khuyen-mai|khuyen_mai|sale|deal|uu-dai|hot-deal|flash-sale|promotion)", "Trang khuyến mãi", 0.95, priority=11),
    # Trang giới thiệu / static
    Rule(r"/(?:gioi-thieu|about|lien-he|contact|chinh-sach|policy|dieu-khoan|faq|help)", "Trang giới thiệu", 0.93, priority=12),
    # Danh mục — segment đầu tiên sau domain (không có segment con)
    Rule(r"^https?://[^/]+/[^/]+/?$", "Danh mục", 0.75, priority=80),
    # Trang sản phẩm — có ≥ 2 segments hoặc kết thúc bằng ID/slug dài
    Rule(r"^https?://[^/]+/[^/]+/[^/]+/?$", "Sản phẩm chi tiết", 0.70, priority=90),
]


class URLClassifier:
    def __init__(
        self,
        rules: list[Rule] | None = None,
        label_config: dict | None = None,
        use_default_fallbacks: bool = True,
    ):
        """
        rules: danh sách Rule (nếu None dùng DEFAULT_RULES)
        label_config: taxonomy đã save từ build_label_taxonomy (override rules)
        use_default_fallbacks: nếu False, bỏ qua các DEFAULT_RULES broad fallback
          (Danh mục priority=80, Sản phẩm chi tiết priority=90) khi label_config được cung cấp
        """
        base_rules = rules if rules is not None else list(DEFAULT_RULES)
        if label_config:
            custom_rules = _rules_from_label_config(label_config)
            default_rules = [r for r in base_rules if r.priority >= 50]
            if not use_default_fallbacks:
                # Loại bỏ các broad fallback rules (priority >= 80) để unlabeled URLs đi qua Claude
                default_rules = [r for r in default_rules if r.priority < 80]
            base_rules = custom_rules + default_rules
        self.rules = sorted(base_rules, key=lambda r: r.priority)

    def classify(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Thêm cột 'label' và 'confidence' vào df.
        Xử lý vectorized — < 2 giây cho 75k rows.
        """
        df = df.copy()
        df["label"] = None
        df["confidence"] = 0.0
        df["method"] = "rule"

        urls: pd.Series = df["url"].str.strip()

        for rule in self.rules:
            unassigned = df["label"].isna()
            if not unassigned.any():
                break
            mask = unassigned & urls.str.contains(rule.pattern, regex=True, flags=rule.flags, na=False)
            df.loc[mask, "label"] = rule.label
            df.loc[mask, "confidence"] = rule.confidence

        return df

    def unlabeled(self, df: pd.DataFrame) -> pd.DataFrame:
        """Trả về các hàng chưa có nhãn sau khi classify."""
        return df[df["label"].isna()].copy()


def _rules_from_label_config(label_config: dict) -> list[Rule]:
    """Chuyển label_config JSON thành Rule objects với priority cao."""
    rules = []
    for i, entry in enumerate(label_config.get("labels", [])):
        for pattern in entry.get("patterns", []):
            rules.append(Rule(
                pattern=pattern,
                label=entry["name"],
                confidence=entry.get("confidence", 0.85),
                priority=i + 1,
            ))
    return rules


def build_classifier(
    label_config: dict | None = None,
    use_default_fallbacks: bool = True,
) -> URLClassifier:
    return URLClassifier(label_config=label_config, use_default_fallbacks=use_default_fallbacks)
