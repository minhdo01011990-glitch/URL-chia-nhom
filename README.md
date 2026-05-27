# url-labeler

Công cụ đánh nhãn URL theo chủ đề nội dung cho phân tích organic traffic SEO.  
Chạy trong **Claude Desktop App** hoặc **Claude Code** — không cần viết code.

Hỗ trợ đến 75,000 hàng. Kết hợp rule-based (miễn phí) + Claude Batch API (~$0.02–0.10).

---

## Cài đặt

### Yêu cầu

- [Python 3.9+](https://python.org/downloads)
- [Claude Desktop App](https://claude.ai/download) **hoặc** [Claude Code](https://claude.ai/code)

---

### Bước 1 — Cài MCP server (terminal)

```bash
pip install url-labeler
url-labeler-install
```

Lệnh `url-labeler-install` tự động đăng ký MCP server vào:
- **Claude Desktop App** — ghi vào `claude_desktop_config.json`
- **Claude Code** — ghi vào `~/.claude/settings.json`

**Sau khi chạy:**

| Môi trường | Cần làm thêm |
|---|---|
| Claude Desktop App | Tắt hoàn toàn (Cmd+Q) rồi mở lại — biểu tượng 🔧 = thành công |
| Claude Code | Không cần làm gì, hoạt động ngay |

---

### Bước 2 — Cài plugin (thủ công)

1. Tải file **`url-labeler.plugin`** từ trang [Releases](https://github.com/minhdo01011990-glitch/URL-chia-nhom/releases/latest)
2. Mở Claude → **Settings → Plugins → Upload file**
3. Chọn file vừa tải → xác nhận

---

## Cài đặt MCP thủ công (nếu `url-labeler-install` không chạy được)

#### Claude Desktop App

| Hệ điều hành | Đường dẫn file cấu hình |
|---|---|
| macOS | `~/Library/Application Support/Claude/claude_desktop_config.json` |
| Windows | `%APPDATA%\Claude\claude_desktop_config.json` |

```json
{
  "mcpServers": {
    "url-labeler": {
      "command": "url-labeler-server"
    }
  }
}
```

#### Claude Code

Thêm vào `~/.claude/settings.json`:

```json
{
  "mcpServers": {
    "url-labeler": {
      "command": "url-labeler-server"
    }
  }
}
```

---

## Sử dụng

### Cách đơn giản nhất

Trong Claude Desktop App hoặc Claude Code, gõ:

```
Đánh nhãn file URL này cho tôi: /Users/ten/data.csv
```

hoặc với Google Sheets:

```
Đánh nhãn file URL này cho tôi: https://docs.google.com/spreadsheets/d/ID/edit
```

Claude sẽ hỏi **4 câu ngắn** rồi tự xử lý:

1. Tên thương hiệu
2. Domain
3. Mục đích phân tích
4. Nhãn mẫu bạn muốn dùng

### Slash commands (sau khi cài plugin)

```
/url-labeler:URL            # Chạy toàn bộ pipeline (khuyến nghị)
/url-labeler:build-labels   # Chỉ xây danh sách nhãn
/url-labeler:label-data     # Chỉ đánh nhãn
/url-labeler:review-labels  # Chỉ review kết quả
```

Kết quả lưu tại `./labeled_output.xlsx` (có thể chỉ định đường dẫn khác).

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
