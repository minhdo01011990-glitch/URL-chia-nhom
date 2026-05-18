# Hướng dẫn sử dụng — url-labeler

Plugin đánh nhãn URL cho phân tích organic traffic SEO, chạy trong **Claude Desktop App**.

---

## Cài đặt (làm 1 lần)

### 1. Cài MCP server

```bash
pip install url-labeler
```

### 2. Cấu hình Claude Desktop App

Mở file (tạo mới nếu chưa có):
- **macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows:** `%APPDATA%\Claude\claude_desktop_config.json`

Nội dung file:

```json
{
  "mcpServers": {
    "url-labeler": {
      "command": "url-labeler-server"
    }
  }
}
```

### 3. Khởi động lại Claude Desktop App

Tắt hoàn toàn → mở lại.  
Biểu tượng 🔧 trong chat = kết nối thành công.

---

## Cách dùng

Trong chat của Claude Desktop App, nhắn:

```
Đánh nhãn file URL này: https://docs.google.com/spreadsheets/d/ID/edit
```

```
Phân tích file này: /Users/ten/data.csv
```

Claude sẽ hỏi **3 câu ngắn**:

```
🏢 [1/3] Tên thương hiệu của website là gì?
→ Ví dụ: Hacom, Thế Giới Di Động

🌐 [2/3] Domain của website?
→ Ví dụ: hacom.vn, thegioididong.com

🏷️  [3/3] Bạn muốn phân loại URL thành những nhãn nào?
→ Nhập 3–10 nhãn mẫu, mỗi dòng một nhãn
   Ví dụ:
     Trang chủ
     Danh mục sản phẩm
     Sản phẩm chi tiết
     Blog - Hướng dẫn
     Trang khuyến mãi
```

Sau đó Claude xác nhận tóm tắt và hỏi **"Bắt đầu đánh nhãn? (y/n)"**.

---

## Quy trình xử lý tự động

```
Tải dữ liệu (CSV / Excel / Google Sheets)
    ↓
Xây danh sách nhãn từ URL patterns + nhãn mẫu của bạn
    ↓
[Bạn review và chỉnh sửa danh sách nhãn]
    ↓
Đánh nhãn bằng quy tắc regex (~85-90% rows, miễn phí)
    ↓
Gửi phần còn lại lên Claude Batch API (Haiku model, ~$0.02-0.10)
    ↓
Xuất kết quả → ~/Downloads/labeled_output.xlsx
    ↓
Hiển thị thống kê + hỗ trợ chỉnh sửa thủ công
```

---

## Định dạng dữ liệu đầu vào

File CSV hoặc Excel cần có 3 cột (tên cột linh hoạt, tự nhận dạng):

| Cột bắt buộc | Tên cột chấp nhận |
|---|---|
| URL | `url`, `link`, `address`, `đường dẫn` |
| Từ khóa | `keywords`, `keyword`, `top keywords`, `từ khóa` |
| Traffic | `organic traffic`, `traffic`, `sessions`, `lượt truy cập` |

**Google Sheets:** chia sẻ ở chế độ "Anyone with the link can view".

---

## Cấu hình API Key

Plugin tự động phát hiện API key theo thứ tự:

1. Biến môi trường `ANTHROPIC_API_KEY` (nếu có)
2. File `~/.anthropic_key` (tự động load khi khởi động)
3. Claude hỏi trực tiếp lần đầu → lưu vào `~/.anthropic_key` → không hỏi lại

Lấy API key tại: **console.anthropic.com → API Keys**

---

## Ước tính thời gian và chi phí

| Số URL | Thời gian rule-based | Thời gian Batch API | Chi phí API |
|---|---|---|---|
| 5,000 | < 2 giây | 10–15 phút | ~$0.005 |
| 20,000 | < 2 giây | 15–20 phút | ~$0.02 |
| 75,000 | < 3 giây | 20–40 phút | ~$0.08 |

Chi phí ước tính với 10–15% hàng cần Claude xử lý. Rule-based không tốn phí API.
