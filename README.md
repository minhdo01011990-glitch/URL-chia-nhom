# url-labeler

Plugin Claude Code để đánh nhãn URL theo chủ đề nội dung cho phân tích organic traffic SEO.  
Xử lý đến 75,000 hàng — kết hợp rule-based (miễn phí) + Claude Batch API (~$0.02–0.10).

---

## Cài đặt nhanh

```bash
# 1. Clone plugin về máy
git clone https://github.com/maytinh/url-labeler ~/url-labeler

# 2. Cài đặt MCP server
pip install ~/url-labeler

# 3. Trong thư mục project SEO của bạn, copy file cấu hình
cp ~/url-labeler/.mcp.json .

# 4. Mở Claude Code với plugin
claude --plugin-dir ~/url-labeler
```

Lần đầu chạy, plugin sẽ hỏi Anthropic API key và tự động lưu vào `~/url-labeler/.anthropic_key`.  
Lấy API key tại: **console.anthropic.com → API Keys**

---

## Sử dụng

```
/url-labeler:start https://docs.google.com/spreadsheets/d/ID/edit
/url-labeler:start /đường/dẫn/data.csv
/url-labeler:start /đường/dẫn/data.xlsx
```

Plugin hỏi **3 câu ngắn** rồi tự động xử lý:

1. **Tên thương hiệu** — ví dụ: `Hacom`, `Thế Giới Di Động`
2. **Domain** — ví dụ: `hacom.vn`, `thegioididong.com`
3. **Nhãn mẫu** — 3–10 nhãn theo cấu trúc bạn muốn (ví dụ: `Trang chủ`, `Danh mục - Máy giặt`, `Blog - Hướng dẫn`)

Kết quả xuất ra `./labeled_output.xlsx`.

---

## Định dạng dữ liệu đầu vào

File CSV / Excel / Google Sheets cần có 3 cột (tên cột nhận dạng tự động):

| URL | Keywords | Organic Traffic |
|-----|----------|-----------------|
| https://example.com/ | trang chủ | 5000 |
| https://example.com/may-giat/ | máy giặt lg | 1200 |

**Google Sheets** cần được chia sẻ ở chế độ "Anyone with the link can view".

---

## Hiệu suất & Chi phí

| Số URL | Rule-based | Claude Batch API | Chi phí |
|--------|-----------|------------------|---------|
| 5,000 | < 2 giây | 10–15 phút | ~$0.005 |
| 20,000 | < 2 giây | 15–20 phút | ~$0.02 |
| 75,000 | < 3 giây | 20–40 phút | ~$0.08 |

85–90% hàng được xử lý bằng rule-based (miễn phí). Chỉ phần còn lại gọi Claude API.

---

## Lệnh độc lập

| Lệnh | Mục đích |
|------|----------|
| `/url-labeler:start [source]` | Toàn bộ pipeline (khuyến nghị) |
| `/url-labeler:build-labels` | Chỉ Bước 1: xây danh sách nhãn |
| `/url-labeler:label-data` | Chỉ Bước 2: đánh nhãn |
| `/url-labeler:review-labels` | Chỉ Bước 3: review và chỉnh sửa |

---

## Yêu cầu

- Python 3.9+
- Claude Code CLI (`npm install -g @anthropic-ai/claude-code` hoặc download tại claude.ai/code)
- Anthropic API key (lấy tại console.anthropic.com)

---

## License

MIT © maytinh
