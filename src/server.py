"""MCP server entry point — wire tất cả 11 tools vào FastMCP."""

from __future__ import annotations

import os
import pathlib
import stat

from fastmcp import FastMCP

from src.tools.io_tools import export_to_excel
from src.tools.io_tools import load_data as _load_data
from src.tools.batch_tools import cancel_stale_batches, force_finalize, merge_batch_results, poll_batch_status, qa_labeled_data, submit_claude_batch
from src.tools.label_tools import apply_rule_based_labels, build_label_taxonomy, save_label_config
from src.tools.review_tools import apply_corrections, get_label_distribution, get_low_confidence_samples

# Lưu API key tại home dir — hoạt động đúng khi server chạy từ Claude Desktop App
_KEY_FILE = pathlib.Path.home() / ".anthropic_key"


def _load_api_key_from_file() -> None:
    """Load ANTHROPIC_API_KEY từ ~/.anthropic_key nếu env var chưa được set."""
    if not os.environ.get("ANTHROPIC_API_KEY") and _KEY_FILE.exists():
        key = _KEY_FILE.read_text().strip()
        if key:
            os.environ["ANTHROPIC_API_KEY"] = key


_load_api_key_from_file()

_INSTRUCTIONS = """
Bạn là trợ lý phân tích SEO, có khả năng đánh nhãn URL theo chủ đề nội dung
(trang chủ, danh mục, sản phẩm, blog...) để phân tích organic traffic.

## Khi nào bắt đầu quy trình
Chỉ bắt đầu khi người dùng cung cấp nguồn dữ liệu URL:
- Link Google Sheets (docs.google.com/spreadsheets/...)
- Đường dẫn file CSV hoặc Excel

Nếu chưa có, hỏi: "Bạn muốn phân tích file nào? (link Google Sheets hoặc đường dẫn CSV/Excel)"

## Bước 0 — Kiểm tra API key
Gọi `check_api_key()` NGAY KHI có nguồn dữ liệu, trước mọi bước khác.
- `configured: true` VÀ `valid: true` → tiếp tục bình thường.
- `configured: true` VÀ `valid: false` → "⚠ API key không hợp lệ hoặc đã hết hạn."
  → Yêu cầu nhập lại: "Nhập API key mới (sk-ant-...):". Khi nhận được → `setup_api_key(api_key=...)`.
- `configured: true` VÀ `valid: null` → "⚠ Không thể xác minh key (mạng chậm?). Key hợp lệ về định dạng."
  → Hỏi: "Tiếp tục với key này? (y/n)"
- `configured: false` → hỏi:
  "🔑 Cần Anthropic API key để gọi Claude Batch API.
   Lấy key tại: console.anthropic.com → API Keys
   Nhập API key của bạn (dạng sk-ant-...):"
  Khi nhận được → `setup_api_key(api_key=...)`.
  Nếu thành công → "✓ API key đã lưu. Sẽ tự động dùng lại ở lần sau."

## Thu thập thông tin (hỏi lần lượt, KHÔNG hỏi cùng lúc)

Câu 1:
  🏢 [1/4] Tên thương hiệu của website là gì?
  Ví dụ: Hacom, Thế Giới Di Động

Câu 2:
  🌐 [2/4] Domain của website?
  Ví dụ: hacom.vn, thegioididong.com

Câu 3:
  🎯 [3/4] Mục đích phân tích của bạn là gì?
  Chọn hoặc mô tả:
    a) Phân tích traffic tổng quan theo nhóm trang — kết quả 5–10 nhãn rộng
    b) Phân loại trang đích cho quảng cáo / landing pages — 15–25 nhãn chi tiết
    c) Phân tích cấu trúc nội dung theo danh mục sản phẩm — 10–20 nhãn theo ngành
    d) Mục đích khác (mô tả ngắn)
  Lưu nguyên văn câu trả lời để truyền vào analysis_goal khi xây nhãn.

Câu 4:
  🏷️ [4/4] Bạn muốn phân loại URL thành những nhãn nào?
  Cung cấp 3–10 nhãn mẫu theo đúng cách bạn muốn đặt tên. Ví dụ:
    Trang chủ
    Danh mục - Máy giặt
    Sản phẩm chi tiết
    Blog - Hướng dẫn
    Trang khuyến mãi
  (mỗi nhãn một dòng, hoặc cách nhau bằng dấu phẩy)

Xác nhận tóm tắt → hỏi: "Bắt đầu đánh nhãn? (y/n)"

## Quy trình xử lý (sau khi user xác nhận y)

### Bước 1 — Xây danh sách nhãn
1. Gọi `load_data(source=...)` → nhận session_id, total_rows
   Báo: "Đang tải dữ liệu... ✓ [total_rows] hàng"
2. Gọi `build_label_taxonomy_tool(session_id, seed_labels=[...], website_description="[brand] ([domain])", analysis_goal="[câu trả lời câu 3]")`
   Số nhãn gợi ý sẽ tự điều chỉnh theo mục đích phân tích.
3. Hiển thị bảng nhãn gợi ý: # | Nhãn | Ví dụ URL | Ước tính số URL
4. **DỪNG — hỏi user, CHỜ phản hồi trước khi gọi bất kỳ tool nào khác:**
   "[S]ử dụng danh sách này | [T]hêm nhãn | [X]óa nhãn | [Đ]ổi tên"
   KHÔNG gọi save_label_config_tool cho đến khi user xác nhận.
5. Xử lý chỉnh sửa nếu có → gọi `save_label_config_tool(session_id, labels=[...])`

### Bước 2 — Đánh nhãn
1. Gọi `apply_rule_based_labels_tool(session_id)`
   Báo: "✓ Đã đánh nhãn [labeled] hàng bằng quy tắc ([coverage_pct]%)"
2. **Kiểm tra phân phối — nếu `imbalanced: true` trong kết quả:**
   Báo: "⚠ Nhãn '[dominant_label]' chiếm [dominant_pct]% URL — có thể cần chia nhỏ hơn."
   Hỏi: "Bạn muốn điều chỉnh danh sách nhãn không? (y/n)"
   Nếu y → quay lại Bước 1: hiển thị lại nhãn hiện tại, nhận chỉnh sửa, gọi `save_label_config_tool` rồi chạy lại `apply_rule_based_labels_tool`.
3. Nếu còn hàng unlabeled:
   - Hiển thị ước tính chi phí
   - Hỏi: "Tiếp tục gửi Claude API? (y / n / --no-claude để bỏ qua)"
   - Nếu y → `submit_claude_batch_tool(session_id)` → poll `poll_batch_status_tool` mỗi 5 phút
     cho đến all_ended=true → `merge_batch_results_tool(session_id)`
   - Nếu --no-claude → `merge_batch_results_tool(session_id)` trực tiếp
4. **Bước QA — Kiểm tra ngẫu nhiên sau khi merge**
   Gọi `qa_sample_labels_tool(session_id)` → kiểm tra ~20 URL qua Claude API
   - `wrong_count = 0` → báo "✓ Kiểm tra ngẫu nhiên: tất cả nhãn hợp lý."
   - `wrong_count > 0` → hiển thị danh sách `wrong_items` (url + current_label + suggested_label)
     Hỏi: "Muốn sửa [N] nhãn sai này không? (y/n)"
     Nếu y → `apply_corrections_tool(session_id, corrections=[{"row_id": ..., "label": suggested_label}, ...])`
5. Hỏi người dùng muốn lưu file ở đâu (mặc định: ~/Downloads/labeled_output.xlsx)
6. Gọi `export_to_excel_tool(session_id, output_path=<đường dẫn>)`
   Báo: "✅ Đã xuất file: [path] ([total_rows] hàng)"

### Bước 3 — Review kết quả
1. Gọi `get_label_distribution_tool(session_id)` → hiển thị bảng thống kê
   - Nếu `warning` không null → hiển thị cảnh báo mất cân bằng
2. Gọi `get_low_confidence_samples_tool(session_id)`
3. Nếu có hàng confidence thấp:
   "⚠ [N] hàng độ tin cậy thấp — xem và chỉnh sửa không? (y/n)"
4. Nếu y → hiển thị danh sách, hướng dẫn: "3 Blog - Kiến thức, 7 Trang khuyến mãi"
5. → `apply_corrections_tool(session_id, corrections=[...])` → `export_to_excel_tool` lại
6. Kết thúc: "✅ Hoàn tất! File đã lưu tại: [path]"

## Xử lý lỗi
- File không tồn tại: thông báo rõ, hỏi lại đường dẫn
- Google Sheets không truy cập được: nhắc chia sẻ sheet ở chế độ "Anyone with the link can view"
- Batch API lỗi: thông báo lỗi, hỏi có muốn bỏ qua bước API không
- Tool timeout (error chứa "timeout" hoặc "timed out"): báo lỗi, hỏi có muốn thử lại không
""".strip()

mcp = FastMCP("url-labeler", instructions=_INSTRUCTIONS)


@mcp.tool()
def load_data(source: str, session_id: str | None = None) -> dict:
    """
    Đọc dữ liệu từ CSV/Excel/Google Sheets.
    source: đường dẫn file hoặc Google Sheets URL.
    Trả về session_id và summary (total_rows, sample 5 hàng, traffic stats).
    """
    return _load_data(source, session_id)


@mcp.tool()
def build_label_taxonomy_tool(
    session_id: str,
    seed_labels: list[str],
    website_description: str = "",
    analysis_goal: str = "",
    use_claude_api: bool = False,
) -> dict:
    """
    Xây danh sách nhãn gợi ý từ URL patterns + seed labels của người dùng.
    seed_labels: 3-10 nhãn mẫu người dùng cung cấp (định nghĩa cấu trúc tên nhãn).
    Trả về danh sách nhãn để Claude trình bày cho người dùng review.
    """
    return build_label_taxonomy(
        session_id, seed_labels, website_description, analysis_goal, use_claude_api
    )


@mcp.tool()
def save_label_config_tool(session_id: str, labels: list[dict]) -> dict:
    """
    Lưu danh sách nhãn đã được người dùng confirm/chỉnh sửa.
    labels: list of {name, patterns, example_url, confidence}.
    """
    return save_label_config(session_id, labels)


@mcp.tool()
def apply_rule_based_labels_tool(
    session_id: str,
    use_default_fallbacks: bool = False,
) -> dict:
    """
    Classify toàn bộ data bằng regex rules (0 token).
    use_default_fallbacks=False (mặc định): URL mơ hồ sẽ được gửi lên Claude Batch API.
    use_default_fallbacks=True: gán generic fallback "Danh mục"/"Sản phẩm" — dùng khi không có API key.
    Trả về số hàng đã label và chưa label.
    """
    return apply_rule_based_labels(session_id, use_default_fallbacks=use_default_fallbacks)


@mcp.tool()
def submit_claude_batch_tool(session_id: str) -> dict:
    """
    Gửi các hàng chưa có nhãn lên Claude Batch API (Haiku model, 50% cheaper).
    Trả về batch_ids và ước tính chi phí.
    """
    return submit_claude_batch(session_id)


@mcp.tool()
def poll_batch_status_tool(session_id: str) -> dict:
    """
    Kiểm tra tiến độ các Claude batches.
    Trả về status và số hàng đã xử lý.
    """
    return poll_batch_status(session_id)


@mcp.tool()
def cancel_stale_batches_tool(session_id: str) -> dict:
    """
    Hủy tất cả batches đang in_progress của session.
    Dùng khi poll_batch_status báo batch treo (stuck_batches trong response).
    Sau khi hủy, gọi submit_claude_batch_tool để submit lại.
    """
    return cancel_stale_batches(session_id)


@mcp.tool()
def merge_batch_results_tool(session_id: str) -> dict:
    """
    Ghép kết quả Claude batch vào rule results.
    Lưu final.parquet. Gọi sau khi poll_batch_status trả về all_ended=true.
    """
    return merge_batch_results(session_id)


@mcp.tool()
def export_to_excel_tool(
    session_id: str,
    output_path: str = "~/Downloads/labeled_output.xlsx",
) -> dict:
    """
    Xuất kết quả cuối cùng ra file Excel.
    output_path mặc định: ~/Downloads/labeled_output.xlsx
    Trả về đường dẫn file và kích thước.
    """
    resolved = str(pathlib.Path(output_path).expanduser())
    return export_to_excel(session_id, resolved)


@mcp.tool()
def get_label_distribution_tool(session_id: str) -> dict:
    """
    Bảng thống kê: nhãn / số URL / % / avg traffic.
    Dùng cho Bước 3 review.
    """
    return get_label_distribution(session_id)


@mcp.tool()
def get_low_confidence_samples_tool(
    session_id: str,
    threshold: float = 0.60,
    max_rows: int = 50,
) -> dict:
    """
    Lọc tối đa 50 hàng có confidence thấp để người dùng review thủ công.
    """
    return get_low_confidence_samples(session_id, threshold, max_rows)


@mcp.tool()
def apply_corrections_tool(session_id: str, corrections: list[dict]) -> dict:
    """
    Áp dụng chỉnh sửa nhãn thủ công.
    corrections: [{"row_id": 42, "label": "Blog - Kiến thức"}, ...]
    """
    return apply_corrections(session_id, corrections)


@mcp.tool()
def check_api_key() -> dict:
    """
    Kiểm tra ANTHROPIC_API_KEY đã cấu hình và hợp lệ bằng cách gọi API thực sự.
    Trả về configured=True/False, valid=True/False/None, và source.
    """
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not (key and key.startswith("sk-ant-")):
        return {
            "configured": False,
            "valid": False,
            "source": "none",
            "key_file_path": str(_KEY_FILE),
            "key_file_exists": _KEY_FILE.exists(),
        }

    source = "file" if _KEY_FILE.exists() else "environment"

    # Test key thực sự với timeout 15 giây — tránh treo khi mạng chậm
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=key, timeout=15.0)
        client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1,
            messages=[{"role": "user", "content": "hi"}],
        )
        return {
            "configured": True,
            "valid": True,
            "source": source,
            "key_file_path": str(_KEY_FILE),
        }
    except anthropic.AuthenticationError:
        return {
            "configured": True,
            "valid": False,
            "source": source,
            "error": "invalid_key",
            "message": "API key không hợp lệ hoặc đã hết hạn. Vui lòng nhập key mới.",
        }
    except anthropic.PermissionDeniedError:
        return {
            "configured": True,
            "valid": False,
            "source": source,
            "error": "permission_denied",
            "message": "API key không có quyền truy cập. Kiểm tra lại key tại console.anthropic.com.",
        }
    except anthropic.RateLimitError:
        # Key hợp lệ nhưng đang bị rate limit — vẫn có thể dùng
        return {
            "configured": True,
            "valid": True,
            "source": source,
            "note": "rate_limited",
            "message": "⚠ API key hợp lệ nhưng đang bị rate limit. Rule-based vẫn chạy được.",
        }
    except TimeoutError:
        return {
            "configured": True,
            "valid": None,
            "source": source,
            "note": "timeout",
            "message": "⚠ Không thể xác minh key trong 15 giây (mạng chậm?). Key hợp lệ về định dạng.",
        }
    except Exception as e:
        err = str(e)
        if "timeout" in err.lower() or "timed out" in err.lower():
            note = "timeout"
            msg = "⚠ Không thể xác minh key (timeout). Key hợp lệ về định dạng."
        else:
            note = "validation_failed"
            msg = f"Không thể xác minh key (lỗi mạng?): {err[:100]}"
        return {
            "configured": True,
            "valid": None,
            "source": source,
            "note": note,
            "message": msg,
        }


@mcp.tool()
def setup_api_key(api_key: str) -> dict:
    """
    Lưu Anthropic API key vào ~/.anthropic_key (chmod 600) và kích hoạt ngay.
    api_key: chuỗi dạng sk-ant-...
    """
    api_key = api_key.strip()
    if not api_key.startswith("sk-ant-"):
        return {
            "success": False,
            "error": "API key không hợp lệ — phải bắt đầu bằng 'sk-ant-'. Lấy key tại console.anthropic.com",
        }

    _KEY_FILE.write_text(api_key)
    _KEY_FILE.chmod(stat.S_IRUSR | stat.S_IWUSR)  # 600
    os.environ["ANTHROPIC_API_KEY"] = api_key

    return {
        "success": True,
        "saved_to": str(_KEY_FILE),
        "message": "API key đã được lưu và kích hoạt. Sẽ tự động load trong các lần chạy tiếp theo.",
    }


@mcp.tool()
def qa_sample_labels_tool(session_id: str, sample_size: int = 20) -> dict:
    """
    Kiểm tra ngẫu nhiên ~20 URL đã đánh nhãn bằng Claude Haiku API.
    Stratified sampling: lấy đều từ mỗi nhãn.
    Trả về wrong_count và wrong_items (kèm row_id để apply_corrections_tool dùng).
    """
    return qa_labeled_data(session_id, sample_size)


def run():
    mcp.run()


if __name__ == "__main__":
    run()
