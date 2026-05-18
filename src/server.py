"""MCP server entry point — wire tất cả 11 tools vào FastMCP."""

from __future__ import annotations

import os
import pathlib
import stat

from fastmcp import FastMCP

from src.tools.io_tools import export_to_excel
from src.tools.io_tools import load_data as _load_data
from src.tools.batch_tools import merge_batch_results, poll_batch_status, submit_claude_batch
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
Gọi `check_api_key()` trước khi làm bất cứ điều gì khác.
- Nếu `configured: true` → tiếp tục.
- Nếu `configured: false` → hỏi:
  "🔑 Cần Anthropic API key để gọi Claude Batch API.
   Lấy key tại: console.anthropic.com → API Keys
   Nhập API key của bạn (dạng sk-ant-...):"
  Khi nhận được → gọi `setup_api_key(api_key=...)`.
  Nếu thành công → "✓ API key đã lưu. Sẽ tự động dùng lại ở lần sau."

## Thu thập thông tin (hỏi lần lượt, không hỏi cùng lúc)

Câu 1:
  🏢 [1/3] Tên thương hiệu của website là gì?
  Ví dụ: Hacom, Thế Giới Di Động

Câu 2:
  🌐 [2/3] Domain của website?
  Ví dụ: hacom.vn, thegioididong.com

Câu 3:
  🏷️ [3/3] Bạn muốn phân loại URL thành những nhãn nào?
  Cung cấp 3–10 nhãn mẫu. Ví dụ:
    Trang chủ
    Danh mục - Máy giặt
    Sản phẩm chi tiết
    Blog - Hướng dẫn
    Trang khuyến mãi
  (mỗi nhãn một dòng, hoặc cách nhau bằng dấu phẩy)

Xác nhận tóm tắt rồi hỏi: "Bắt đầu đánh nhãn? (y/n)"

## Quy trình xử lý (sau khi user xác nhận y)

### Bước 1 — Xây danh sách nhãn
1. Gọi `load_data(source=...)` → nhận session_id, total_rows
   Báo: "Đang tải dữ liệu... ✓ [total_rows] hàng"
2. Gọi `build_label_taxonomy_tool(session_id, seed_labels=[...], website_description="[brand] ([domain])", analysis_goal="")`
3. Hiển thị bảng nhãn gợi ý:
   # | Nhãn | Ví dụ URL | Ước tính
4. Hỏi: "[S]ử dụng | [T]hêm nhãn | [X]óa nhãn | [Đ]ổi tên"
5. Xử lý chỉnh sửa nếu có → gọi `save_label_config_tool(session_id, labels=[...])`

### Bước 2 — Đánh nhãn
1. Gọi `apply_rule_based_labels_tool(session_id)`
   Báo: "✓ Đã đánh nhãn [labeled] hàng bằng quy tắc ([coverage_pct]%)"
2. Nếu còn hàng unlabeled:
   - Hiển thị ước tính chi phí
   - Hỏi: "Tiếp tục gửi Claude API? (y / n / --no-claude để bỏ qua)"
   - Nếu y → `submit_claude_batch_tool(session_id)` → poll `poll_batch_status_tool` mỗi 5 phút
     cho đến all_ended=true → `merge_batch_results_tool(session_id)`
   - Nếu --no-claude → `merge_batch_results_tool(session_id)` trực tiếp
3. Hỏi người dùng muốn lưu file ở đâu (mặc định: ~/Downloads/labeled_output.xlsx)
4. Gọi `export_to_excel_tool(session_id, output_path=<đường dẫn>)`
   Báo: "✅ Đã xuất file: [path] ([total_rows] hàng)"

### Bước 3 — Review kết quả
1. Gọi `get_label_distribution_tool(session_id)` → hiển thị bảng thống kê
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
def apply_rule_based_labels_tool(session_id: str) -> dict:
    """
    Classify toàn bộ data bằng regex rules (~85-90% coverage, 0 token).
    Trả về số hàng đã label và chưa label.
    """
    return apply_rule_based_labels(session_id)


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
    Kiểm tra xem ANTHROPIC_API_KEY đã được cấu hình chưa.
    Trả về configured=True/False và source (env / file / none).
    """
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    configured = bool(key and key.startswith("sk-ant-"))
    return {
        "configured": configured,
        "source": "file" if (configured and _KEY_FILE.exists()) else ("environment" if configured else "none"),
        "key_file_path": str(_KEY_FILE),
        "key_file_exists": _KEY_FILE.exists(),
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


def run():
    mcp.run()


if __name__ == "__main__":
    run()
