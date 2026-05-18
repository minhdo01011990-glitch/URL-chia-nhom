# Hướng dẫn sử dụng Plugin URL Labeler

Plugin tự động phân loại URL theo nội dung trang (trang chủ, danh mục, sản phẩm, blog...) để phân tích organic traffic SEO. Xử lý được tới 75,000 hàng.

---

## Cách kích hoạt

### Cách 1 — Kích hoạt trực tiếp với link dữ liệu (khuyến nghị)

Cung cấp nguồn dữ liệu ngay trong lệnh gọi:

```
/url-labeler:start https://docs.google.com/spreadsheets/d/ID_SHEET/edit
```

```
/url-labeler:start /Users/ten/data.csv
```

```
/url-labeler:start /Users/ten/data.xlsx
```

### Cách 2 — Kích hoạt rồi cung cấp link sau

```
/url-labeler:start
```

Agent sẽ hỏi bạn link dữ liệu ở bước đầu tiên.

---

## Quy trình sau khi kích hoạt

Sau khi nhận được nguồn dữ liệu, agent hỏi **3 câu ngắn**:

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

Sau đó agent xác nhận tóm tắt và hỏi "Bắt đầu đánh nhãn? (y/n)".

---

## Quy trình xử lý tự động

```
Tải dữ liệu (CSV / Excel / Google Sheets)
    ↓
Xây danh sách nhãn từ URL patterns + nhãn mẫu của bạn
    ↓
[Bạn review và chỉnh sửa danh sách nhãn]
    ↓
Đánh nhãn bằng quy tắc regex (~85-90% rows, 0 chi phí)
    ↓
Gửi phần còn lại lên Claude Batch API (Haiku model, ~$0.02-0.10)
    ↓
Xuất kết quả → ./labeled_output.xlsx
    ↓
Hiển thị thống kê + hỗ trợ chỉnh sửa thủ công
```

---

## Định dạng dữ liệu đầu vào

File CSV hoặc Excel cần có 3 cột (tên cột linh hoạt, plugin tự nhận dạng):

| Cột bắt buộc | Tên cột chấp nhận |
|---|---|
| URL | `url`, `link`, `address`, `đường dẫn` |
| Từ khóa | `keywords`, `keyword`, `top keywords`, `top keyword`, `từ khóa` |
| Traffic | `organic traffic`, `traffic`, `sessions`, `lượt truy cập` |

**Google Sheets:** Sheet cần được chia sẻ ở chế độ "Anyone with the link can view".

---

## Lệnh bổ sung (chạy từng bước riêng lẻ)

| Lệnh | Mục đích |
|---|---|
| `/url-labeler:start [source]` | Chạy toàn bộ pipeline (khuyến nghị) |
| `/url-labeler:build-labels` | Chỉ Bước 1: xây danh sách nhãn |
| `/url-labeler:label-data --session=<id>` | Chỉ Bước 2: đánh nhãn (tiếp tục session cũ) |
| `/url-labeler:review-labels --session=<id>` | Chỉ Bước 3: review và chỉnh sửa |

---

## Ước tính thời gian và chi phí

| Số URL | Thời gian rule-based | Thời gian Batch API | Chi phí API |
|---|---|---|---|
| 5,000 | < 2 giây | 10-15 phút | ~$0.005 |
| 20,000 | < 2 giây | 15-20 phút | ~$0.02 |
| 75,000 | < 3 giây | 20-40 phút | ~$0.08 |

Chi phí ước tính với 10-15% hàng cần Claude xử lý. Rule-based không tốn chi phí API.

---

## Cấu hình API Key

Plugin tự động phát hiện API key theo thứ tự ưu tiên:

1. **Biến môi trường** `ANTHROPIC_API_KEY` (nếu đã export trong shell)
2. **File `~/.anthropic_key`** — plugin tự load khi khởi động (không cần export mỗi lần)
3. **Hỏi trực tiếp** — nếu cả hai đều chưa có, agent sẽ hỏi và tự động lưu vào `~/.anthropic_key`

**Cách thiết lập lần đầu (nếu chưa có):**

```
/url-labeler:start https://...
→ Plugin hỏi: "Nhập API key của bạn (dạng sk-ant-...):"
→ Nhập key → tự động lưu vào .anthropic_key trong thư mục project (chmod 600)
→ Các lần chạy sau không cần nhập lại
```

**Hoặc thiết lập thủ công:**

```bash
# Tạo file trong thư mục project
echo "sk-ant-..." > /đường/dẫn/tới/URL-chia-nhom/.anthropic_key
chmod 600 /đường/dẫn/tới/URL-chia-nhom/.anthropic_key
```

> File `.anthropic_key` đã được thêm vào `.gitignore` — sẽ không bị commit lên Git.

**Google Sheets** (chỉ cần nếu sheet không public):

```bash
export GOOGLE_SERVICE_ACCOUNT_JSON="/path/to/service-account.json"
```

---

## Cài đặt

```bash
pip install url-labeler
```

Thêm vào `.mcp.json` trong thư mục dự án:

```json
{
  "mcpServers": {
    "url-labeler": {
      "command": "url-labeler-server",
      "env": {
        "ANTHROPIC_API_KEY": "${ANTHROPIC_API_KEY}"
      }
    }
  }
}
```
