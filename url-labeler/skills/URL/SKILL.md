---
name: URL
description: >
  This skill should be used when the user wants to "label URLs", "classify URLs",
  "phân loại URL", "gán nhãn URL", "bắt đầu phân tích SEO", "start URL labeling",
  "run the full URL labeling pipeline", or any request to categorize a list of URLs
  by content type for SEO or traffic analysis purposes. Triggers the complete
  guided pipeline from data ingestion to labeled Excel output.
metadata:
  version: "0.1.0"
---

# URL Labeler — Full Pipeline Coordinator

Conduct a structured **intake dialog** before calling any MCP tools. Do not load data or run any processing until the user has confirmed the summary at the end of the dialog.

## Bước 0 — Kiểm tra API key (trước intake dialog)

Gọi `check_api_key()` ngay khi skill được kích hoạt.

- Nếu `configured: true` → bỏ qua, chuyển thẳng sang Question 1.
- Nếu `configured: false` → hỏi như sau trước Question 1:

> 🔑 **API key Anthropic** dùng để phân loại các URL mà quy tắc không xác định được (~10–15% hàng).
> Lấy key tại: [console.anthropic.com → API Keys](https://console.anthropic.com)
> Nhập API key của bạn (dạng `sk-ant-...`):

Khi nhận được key → gọi `setup_api_key(api_key=...)`.
- Nếu thành công → "✓ API key đã lưu. Sẽ tự động dùng lại ở lần sau." → tiếp tục Question 1.
- Nếu user bỏ qua (gõ "skip" hoặc không nhập) → thông báo: "Sẽ chỉ dùng phân loại rule-based (~85–90% URL). Có thể thêm key sau." → tiếp tục Question 1.

## Intake Dialog (run in order, one question at a time)

### Question 1 — Data source

Ask the user where their URL data comes from. Accepted formats:

- **File path** — Excel (.xlsx, .xls), CSV, TSV, JSON (array of URLs or objects with a URL field)
- **Google Sheets URL** — share link with at least viewer access
- **NotebookLM export** — markdown (.md) or plain text (.txt) exported from NotebookLM containing a list of URLs (one per line, or in a table/list structure)
- **Clipboard / paste** — user pastes raw URL list directly into the chat

For NotebookLM exports: inform the user that the tool will auto-detect URLs from the exported markdown structure (lists, tables, footnotes). Ask them to confirm which field/column contains the URLs if the export has multiple columns.

Reference `references/input-formats.md` for detailed parsing rules per format.

### Question 2 — Website domain

Ask: "Domain của website là gì?" (ví dụ: `hacom.vn`, `thegioididong.com`)

Domain được dùng để research trực tiếp cấu trúc và sản phẩm trên website — không cần mô tả thủ công.

### Question 3 — Analysis goal

Ask: "What do you want to understand from this analysis?" Examples:
- Which URL types drive the most organic traffic?
- Compare performance between product pages and blog posts
- Identify thin-content pages

The goal shapes label suggestions and the final report structure.

### Question 4 — Seed labels

Ask the user to provide **3–10 example labels** in their preferred naming style. These are the most important input — they define naming conventions and act as few-shot examples.

Example seeds (Vietnamese e-commerce style):
- "Trang chủ"
- "Danh mục - Máy giặt"
- "Sản phẩm - Máy giặt Toshiba 9kg"
- "Blog - Kiến thức"
- "Trang tĩnh - Liên hệ"

Remind the user: new labels will follow the same naming pattern as their seeds.

### Question 5 — Output path

Ask where to save the labeled Excel file. Default: `./labeled_output.xlsx`. Accept any writable path.

### Question 6 — Notes (optional)

Ask:

> 📝 **[6/6] Lưu ý thêm** _(tùy chọn — nhấn Enter để bỏ qua)_
> Có điều chỉnh đặc biệt nào không? Ví dụ:
> - "Bỏ qua các URL chứa /admin/ hoặc /test/"
> - "Tối đa 8 nhãn, không tạo thêm"
> - "Nhãn phải viết tiếng Anh"
> - "Sản phẩm điều hòa là ưu tiên cao nhất"
> - "Không gọi Claude API, chỉ dùng rule-based"

If the user skips (presses Enter or says "không" / "skip" / "bỏ qua"), set `notes = null` and continue.

---

## Confirmation Summary

After collecting all answers, present a summary table:

```
📋 Summary
─────────────────────────────────────
API key:       ✓ Đã cấu hình  (hoặc "⚠ Chưa có — chỉ dùng rule-based")
Data source:   [path/URL/format]
Domain:        [domain] → sẽ research cấu trúc website tự động
Goal:          [analysis goal]
Seed labels:   [label 1], [label 2], ...
Output:        [path]
Notes:         [nội dung lưu ý]  (hoặc bỏ trống nếu không có)
─────────────────────────────────────
Ready to start? (yes / adjust)
```

Only proceed after explicit user confirmation.

---

## Applying Notes Throughout the Pipeline

If `notes` is not null, parse and apply it at each relevant step before calling any MCP tool:

| Note type | When to apply | How to apply |
|---|---|---|
| Exclude URL patterns (e.g. "bỏ qua /admin/") | Step 1 — `load_data` | Mention to the user that matching URLs will be tagged as `[excluded]` in the output |
| Label count limit (e.g. "tối đa 8 nhãn") | Step 2 — `build_label_taxonomy` | Pass as a constraint when presenting the taxonomy; remove lowest-frequency labels until the count is met |
| Language constraint (e.g. "nhãn tiếng Anh") | Step 2 — `build_label_taxonomy` | Translate or rename all suggested labels before presenting for review |
| Priority category (e.g. "ưu tiên điều hòa") | Step 2 — `build_label_taxonomy` | Ensure a dedicated label exists for that category; mention it first in the taxonomy table |
| Skip Claude API (e.g. "chỉ rule-based") | Step 6 — `submit_claude_batch` | Skip this step entirely; note that ~10–15% of rows will remain as `[unclassified]` |
| Any other instruction | Most relevant step | Apply the instruction at the step where it has the most effect; if ambiguous, apply at Step 2 |

After applying a note at a step, briefly confirm to the user: "✓ Đã áp dụng lưu ý: [nội dung]."

If a note contradicts another input (e.g. notes say "max 5 labels" but seed labels already have 8), surface the conflict and ask the user to confirm which takes priority before continuing.

---

## Processing Pipeline (after confirmation)

Call MCP tools in this order:

1. `load_data` — pass file path or URL; specify `source_format` (see `references/input-formats.md`)
2. `build_label_taxonomy` — pass `seed_labels`, website description, and analysis goal
3. **STOP — present taxonomy table to user and wait for explicit confirmation before continuing:**
   - Display: `# | Nhãn | Ví dụ URL | Ước tính | Nguồn`
   - Ask: "[S]ử dụng danh sách này | [T]hêm nhãn | [X]óa nhãn | [Đ]ổi tên"
   - **Do NOT call `save_label_config` until the user replies.**
   - Process any edits the user requests (add/remove/rename labels).
4. `save_label_config` — call only after user confirms with [S] or after edits are done
5. `apply_rule_based_labels` — rule-based pass (~85–90% of rows, 0 tokens)
6. `submit_claude_batch` — send ambiguous rows to Batch API (Haiku model)
7. **STOP — present polling options, do NOT call any tool until user responds:**

   ```
   📤 Đã gửi [X] hàng lên Batch API ([N] batch)
   Session: [session_id]
   Chi phí ước tính: ~$[cost]
   Thời gian xử lý thông thường: 10–30 phút

   Chọn cách theo dõi kết quả:
   ──────────────────────────────────────────────
   [A] Tự động — kiểm tra sau:  10 / 15 / 20 / 25 / 30  phút
   [B] Thủ công — tôi tự theo dõi, sẽ báo lại khi xong
   ──────────────────────────────────────────────
   ```

   **[A] Auto**: Sau đúng khoảng thời gian user chọn, gọi `poll_batch_status` **đúng 1 lần**. Nếu chưa xong → hỏi chờ thêm hay chuyển thủ công. Không bao giờ poll nhiều lần trong cùng 1 lượt.

   **[B] Thủ công**: Lưu session_id, chờ user báo "batch xong rồi" → gọi `poll_batch_status` **đúng 1 lần** để xác nhận trước khi merge.

8. `merge_batch_results` — merge batch results back (chỉ gọi sau khi `all_ended: true`)
9. `export_to_excel` — write final output
10. `get_label_distribution` — show distribution summary to user
11. Offer optional `get_low_confidence_samples` for review

## Resume Behavior

If the user says "resume session [session_id]" or references a previous run, skip the intake dialog and call `poll_batch_status` or `merge_batch_results` directly using the stored session_id.

## Token Budget Rule

Never display raw data rows in the conversation. Return only: row counts, label names, confidence scores, and small samples (≤10 rows for load confirmation, ≤50 rows for review).
