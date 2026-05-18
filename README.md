# url-labeler

Công cụ đánh nhãn URL theo chủ đề nội dung cho phân tích organic traffic SEO.  
Chạy trực tiếp trong **Claude Desktop App** — không cần viết code, không cần terminal.

Hỗ trợ đến 75,000 hàng. Kết hợp rule-based (miễn phí) + Claude Batch API (~$0.02–0.10).

---

## Cài đặt

### Yêu cầu
- [Python 3.9+](https://python.org/downloads)
- [Claude Desktop App](https://claude.ai/download) — tải về và cài đặt

### Bước 1 — Cài MCP server

Mở Terminal và chạy:

```bash
pip install url-labeler
```

### Bước 2 — Thêm vào Claude Desktop App

Mở file cấu hình của Claude Desktop App:

| Hệ điều hành | Đường dẫn |
|---|---|
| macOS | `~/Library/Application Support/Claude/claude_desktop_config.json` |
| Windows | `%APPDATA%\Claude\claude_desktop_config.json` |

Thêm đoạn sau vào file (nếu file chưa có thì tạo mới):

```json
{
  "mcpServers": {
    "url-labeler": {
      "command": "url-labeler-server"
    }
  }
}
```

> Nếu file đã có `mcpServers` với server khác, chỉ cần thêm phần `"url-labeler": {...}` vào trong.

### Bước 3 — Khởi động lại Claude Desktop App

Tắt hoàn toàn và mở lại Claude Desktop App.  
Biểu tượng 🔧 xuất hiện trong chat = plugin đã kết nối thành công.

---

## Sử dụng

Mở chat trong Claude Desktop App và gõ:

```
Hãy đánh nhãn file URL này cho tôi: https://docs.google.com/spreadsheets/d/ID/edit
```

hoặc:

```
Đánh nhãn file /Users/ten/data.csv
```

Claude sẽ tự động hỏi **3 câu ngắn** rồi xử lý:

1. Tên thương hiệu
2. Domain
3. Nhãn mẫu bạn muốn dùng

Kết quả lưu tại `~/Downloads/labeled_output.xlsx` (có thể chỉ định đường dẫn khác).

---

## Định dạng dữ liệu đầu vào

File CSV / Excel / Google Sheets cần có 3 cột (tên cột nhận dạng tự động):

| URL | Keywords | Organic Traffic |
|-----|----------|-----------------|
| https://example.com/ | trang chủ | 5000 |
| https://example.com/may-giat/ | máy giặt lg | 1200 |

**Google Sheets:** chia sẻ ở chế độ "Anyone with the link can view".

---

## API Key

Lần đầu chạy, Claude sẽ hỏi Anthropic API key.  
Lấy key tại: **console.anthropic.com → API Keys**

Key được lưu tại `~/.anthropic_key` — các lần sau không cần nhập lại.

---

## Hiệu suất & Chi phí

| Số URL | Rule-based | Claude Batch API | Chi phí API |
|--------|-----------|------------------|-------------|
| 5,000 | < 2 giây | 10–15 phút | ~$0.005 |
| 20,000 | < 2 giây | 15–20 phút | ~$0.02 |
| 75,000 | < 3 giây | 20–40 phút | ~$0.08 |

85–90% hàng xử lý bằng rule-based (miễn phí). Chỉ phần còn lại gọi Claude API.

---

## License

MIT © maytinh
