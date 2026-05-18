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

# Project root = thư mục chứa src/ (tức /Users/.../URL-chia-nhom/)
_PROJECT_ROOT = pathlib.Path(__file__).parent.parent
_KEY_FILE = _PROJECT_ROOT / ".anthropic_key"


def _load_api_key_from_file() -> None:
    """Load ANTHROPIC_API_KEY from <project>/.anthropic_key if env var not set."""
    if not os.environ.get("ANTHROPIC_API_KEY") and _KEY_FILE.exists():
        key = _KEY_FILE.read_text().strip()
        if key:
            os.environ["ANTHROPIC_API_KEY"] = key


_load_api_key_from_file()

mcp = FastMCP("url-labeler", instructions=(
    "MCP server cho plugin url-labeler. "
    "Xử lý đánh nhãn URL theo chủ đề nội dung cho phân tích SEO organic traffic. "
    "Tất cả dữ liệu thô được xử lý tại đây — không trả raw rows về Claude Code context."
))


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
def export_to_excel_tool(session_id: str, output_path: str = "./labeled_output.xlsx") -> dict:
    """
    Xuất kết quả cuối cùng ra file Excel.
    Trả về đường dẫn file và kích thước.
    """
    return export_to_excel(session_id, output_path)


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
    File lưu tại <project>/.anthropic_key (cùng thư mục project).
    """
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    configured = bool(key and key.startswith("sk-ant-"))
    if configured:
        source = "file" if _KEY_FILE.exists() else "environment"
    else:
        source = "none"
    return {
        "configured": configured,
        "source": source,
        "key_file_path": str(_KEY_FILE),
        "key_file_exists": _KEY_FILE.exists(),
    }


@mcp.tool()
def setup_api_key(api_key: str) -> dict:
    """
    Lưu Anthropic API key vào <project>/.anthropic_key (chmod 600) và kích hoạt ngay cho session này.
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
