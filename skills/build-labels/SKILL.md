---
description: Chỉ chạy Bước 1 — xây dựng và review danh sách nhãn. Dùng khi bạn đã có session_id hoặc muốn xây nhãn riêng trước khi đánh nhãn.
---

# Bước 1: Xây dựng danh sách nhãn

Bước này phân tích cấu trúc URL và xây danh sách nhãn phù hợp với website của bạn.

## Cách dùng

Nếu bạn chưa có session:
```
/url-labeler:build-labels
```
Tôi sẽ hỏi: nguồn dữ liệu, mô tả website, mục tiêu, và nhãn mẫu.

Nếu đã có session:
```
/url-labeler:build-labels --session=<session_id>
```

## Quy trình

1. Tải dữ liệu (`load_data`)
2. Phân tích URL patterns và xây taxonomy từ seed labels (`build_label_taxonomy_tool`)
3. Trình bày danh sách nhãn gợi ý để bạn review/chỉnh sửa
4. Lưu taxonomy đã confirm (`save_label_config_tool`)

Sau bước này, dùng `/url-labeler:label-data --session=<id>` để đánh nhãn.

---

Hãy bắt đầu. Bạn có session_id sẵn không, hay cần tạo mới?

Nếu tạo mới, cho tôi biết:
1. Nguồn dữ liệu (file path hoặc Google Sheets URL)
2. Nhãn mẫu bạn muốn dùng (3-10 nhãn theo cấu trúc bạn thích)
