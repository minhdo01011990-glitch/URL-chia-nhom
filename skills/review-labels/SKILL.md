---
description: Chỉ chạy Bước 3 — xem thống kê kết quả và chỉnh sửa nhãn thủ công. Yêu cầu đã có session với final.parquet.
---

# Bước 3: Review và chỉnh sửa nhãn

Bước này hiển thị thống kê phân phối nhãn và hỗ trợ chỉnh sửa các hàng có độ tin cậy thấp.

## Cách dùng

```
/url-labeler:review-labels --session=<session_id>
```

## Quy trình

Cho tôi biết `session_id`, tôi sẽ:

1. Lấy thống kê phân phối nhãn (`get_label_distribution_tool`)
2. Lọc hàng có confidence thấp (`get_low_confidence_samples_tool`)
3. Để bạn chỉnh sửa nhãn qua hội thoại
4. Áp dụng corrections và xuất lại Excel nếu có thay đổi

## Cú pháp chỉnh sửa

Khi thấy danh sách hàng confidence thấp, nhập theo dạng:
```
3 Blog - Kiến thức, 7 Trang khuyến mãi
```
(số thứ tự trong danh sách + tên nhãn mới)

---

Session ID của bạn là gì?
