---
description: Chỉ chạy Bước 2 — đánh nhãn dữ liệu. Yêu cầu đã có session với label_config được lưu từ Bước 1.
---

# Bước 2: Đánh nhãn dữ liệu

Bước này áp dụng nhãn cho toàn bộ dữ liệu theo 2 giai đoạn:
- **Rule-based**: ~85-90% rows, 0 token, < 2 giây
- **Claude Batch API**: phần còn lại (~10-15%), Haiku model, tối ưu token tối đa

## Tối ưu token trong Claude Batch API

- **Prompt caching**: system prompt (danh sách nhãn) được cache và chia sẻ toàn batch → giảm 90% chi phí system prompt
- **Label index**: model trả về số thứ tự (`2`) thay vì tên đầy đủ (`Danh mục - Tủ lạnh`) → giảm output tokens ~8x
- **Compact input**: chỉ gửi URL path + 60 ký tự keywords đầu tiên → giảm input ~60%

Tổng tiết kiệm: ~70% chi phí so với cách gọi thông thường.

## Cách dùng

```
/url-labeler:label-data --session=<session_id>
```

## Quy trình

Cho tôi biết `session_id` của bạn (từ Bước 1), tôi sẽ:

1. Classify bằng rule-based (`apply_rule_based_labels_tool`)
2. Gửi hàng chưa xác định lên Claude Batch API (`submit_claude_batch_tool`)
3. Chờ kết quả — poll mỗi 5 phút (`poll_batch_status_tool` → `merge_batch_results_tool`)
4. Xuất Excel (`export_to_excel_tool`)

Nếu muốn bỏ qua Claude API: thêm `--no-claude`

---

Session ID của bạn là gì?
