"""Unit tests cho rule-based URL classifier."""

import pandas as pd
import pytest

from src.core.classifier import URLClassifier, build_classifier


def make_df(urls: list[str]) -> pd.DataFrame:
    return pd.DataFrame({
        "url": urls,
        "keywords": ["test"] * len(urls),
        "traffic": [100] * len(urls),
    })


@pytest.fixture
def clf():
    return build_classifier()


class TestHomepage:
    def test_root_url(self, clf):
        df = clf.classify(make_df(["https://example.com/"]))
        assert df.iloc[0]["label"] == "Trang chủ"
        assert df.iloc[0]["confidence"] == 1.0

    def test_root_no_slash(self, clf):
        df = clf.classify(make_df(["https://example.com"]))
        assert df.iloc[0]["label"] == "Trang chủ"

    def test_index_html(self, clf):
        df = clf.classify(make_df(["https://example.com/index.html"]))
        assert df.iloc[0]["label"] == "Trang chủ"

    def test_trang_chu_slug(self, clf):
        df = clf.classify(make_df(["https://example.com/trang-chu"]))
        assert df.iloc[0]["label"] == "Trang chủ"


class TestTransaction:
    def test_cart(self, clf):
        df = clf.classify(make_df(["https://example.com/cart"]))
        assert df.iloc[0]["label"] == "Trang giao dịch"

    def test_gio_hang(self, clf):
        df = clf.classify(make_df(["https://example.com/gio-hang/"]))
        assert df.iloc[0]["label"] == "Trang giao dịch"

    def test_checkout(self, clf):
        df = clf.classify(make_df(["https://shop.vn/checkout/payment"]))
        assert df.iloc[0]["label"] == "Trang giao dịch"


class TestSearch:
    def test_search_en(self, clf):
        df = clf.classify(make_df(["https://example.com/search?q=laptop"]))
        assert df.iloc[0]["label"] == "Trang tìm kiếm"

    def test_tim_kiem(self, clf):
        df = clf.classify(make_df(["https://example.com/tim-kiem"]))
        assert df.iloc[0]["label"] == "Trang tìm kiếm"


class TestBlog:
    def test_blog_segment(self, clf):
        df = clf.classify(make_df(["https://example.com/blog/bai-viet-hay"]))
        assert df.iloc[0]["label"] == "Blog"

    def test_tin_tuc(self, clf):
        df = clf.classify(make_df(["https://example.com/tin-tuc/su-kien-2024"]))
        assert df.iloc[0]["label"] == "Blog"

    def test_kien_thuc(self, clf):
        df = clf.classify(make_df(["https://example.com/kien-thuc/may-giat"]))
        assert df.iloc[0]["label"] == "Blog"


class TestPromo:
    def test_khuyen_mai(self, clf):
        df = clf.classify(make_df(["https://example.com/khuyen-mai/tet-2024"]))
        assert df.iloc[0]["label"] == "Trang khuyến mãi"

    def test_sale(self, clf):
        df = clf.classify(make_df(["https://example.com/sale"]))
        assert df.iloc[0]["label"] == "Trang khuyến mãi"


class TestStatic:
    def test_gioi_thieu(self, clf):
        df = clf.classify(make_df(["https://example.com/gioi-thieu"]))
        assert df.iloc[0]["label"] == "Trang giới thiệu"

    def test_lien_he(self, clf):
        df = clf.classify(make_df(["https://example.com/lien-he"]))
        assert df.iloc[0]["label"] == "Trang giới thiệu"

    def test_policy(self, clf):
        df = clf.classify(make_df(["https://example.com/chinh-sach-bao-mat"]))
        assert df.iloc[0]["label"] == "Trang giới thiệu"


class TestCategory:
    def test_single_segment(self, clf):
        df = clf.classify(make_df(["https://example.com/may-giat/"]))
        assert df.iloc[0]["label"] == "Danh mục"

    def test_single_segment_no_slash(self, clf):
        df = clf.classify(make_df(["https://example.com/tu-lanh"]))
        assert df.iloc[0]["label"] == "Danh mục"


class TestProduct:
    def test_two_segments(self, clf):
        df = clf.classify(make_df(["https://example.com/may-giat/lg-wm1234.html"]))
        assert df.iloc[0]["label"] == "Sản phẩm chi tiết"

    def test_nested_product(self, clf):
        df = clf.classify(make_df(["https://example.com/dien-lanh/may-lanh-daikin-ftka25uavmv"]))
        assert df.iloc[0]["label"] == "Sản phẩm chi tiết"


class TestPriority:
    def test_blog_beats_category(self, clf):
        """Blog URL có 2 segments — phải được nhận dạng là Blog, không phải Sản phẩm chi tiết."""
        df = clf.classify(make_df(["https://example.com/blog/huong-dan-chon-tu-lanh"]))
        assert df.iloc[0]["label"] == "Blog"

    def test_checkout_beats_product(self, clf):
        df = clf.classify(make_df(["https://example.com/checkout/confirm"]))
        assert df.iloc[0]["label"] == "Trang giao dịch"


class TestVectorized:
    def test_large_batch_performance(self, clf):
        """75k rows phải classify xong trong < 5 giây."""
        import time
        urls = [
            "https://example.com/",
            "https://example.com/may-giat/",
            "https://example.com/may-giat/lg-1234",
            "https://example.com/blog/bai-viet",
            "https://example.com/cart",
        ] * 15_000
        df = make_df(urls)
        start = time.time()
        result = clf.classify(df)
        elapsed = time.time() - start
        assert elapsed < 5.0, f"Classify 75k rows mất {elapsed:.1f}s > 5s"
        assert result["label"].notna().sum() == len(result)


class TestCustomLabelConfig:
    def test_custom_patterns_override_defaults(self):
        config = {
            "labels": [
                {
                    "name": "Danh mục - Máy giặt",
                    "patterns": [r"/may-giat/?$"],
                    "confidence": 0.95,
                },
                {
                    "name": "Sản phẩm - Máy giặt",
                    "patterns": [r"/may-giat/.+"],
                    "confidence": 0.90,
                },
            ]
        }
        clf = build_classifier(label_config=config)
        df = clf.classify(make_df([
            "https://example.com/may-giat/",
            "https://example.com/may-giat/lg-fw1234",
        ]))
        assert df.iloc[0]["label"] == "Danh mục - Máy giặt"
        assert df.iloc[1]["label"] == "Sản phẩm - Máy giặt"
