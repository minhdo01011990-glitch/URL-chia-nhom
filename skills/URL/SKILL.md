---
description: Đánh nhãn dữ liệu URL cho phân tích SEO. Kích hoạt bằng cách cung cấp file CSV/Excel hoặc link Google Sheets cần phân tích.
agent: label-coordinator
---

Kích hoạt `label-coordinator` agent để bắt đầu quy trình đánh nhãn URL.

**Cách dùng:** Cung cấp nguồn dữ liệu khi gọi lệnh:
```
/url-labeler:URL https://docs.google.com/spreadsheets/d/...
/url-labeler:URL /đường/dẫn/file.csv
/url-labeler:URL /đường/dẫn/file.xlsx
```

Agent sẽ:
1. Nhận nguồn dữ liệu từ lệnh gọi
2. Hỏi 3 câu ngắn: tên thương hiệu, domain, nhãn mẫu
3. Xây danh sách nhãn phù hợp và để người dùng review
4. Tự động đánh nhãn (rule-based + Claude Batch API nếu cần)
5. Xuất kết quả ra `./labeled_output.xlsx`
6. Trình bày thống kê và hỗ trợ chỉnh sửa thủ công
