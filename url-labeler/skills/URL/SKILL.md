---
name: URL
description: >
  This skill should be used when the user wants to "label URLs", "classify URLs",
  "phân loại URL", "gán nhãn URL", "bắt đầu phân tích SEO", "start URL labeling",
  "run the full URL labeling pipeline", or any request to categorize a list of URLs
  by content type for SEO or traffic analysis purposes. Runs the complete guided
  pipeline from data ingestion to labeled Excel output.
metadata:
  version: "2.0.0"
---

# URL Labeler — Full Pipeline

Conduct a structured **intake dialog** before calling any MCP tools. Do not load data or run any processing until the user has confirmed the summary at the end of the dialog.

---

## Bước 0 — Kiểm tra API key

Gọi `check_api_key()` ngay khi skill được kích hoạt.

- `configured: true` và `valid: true` → tiếp tục Question 1.
- `configured: true` và `valid: false` → "⚠ API key không hợp lệ. Nhập key mới (sk-ant-...):" → gọi `setup_api_key(api_key=...)`.
- `configured: true` và `valid: null` → "⚠ Không xác minh được key (mạng chậm?). Tiếp tục với key này? (y/n)"
- `configured: false` → hỏi:
  > 🔑 Cần Anthropic API key để phân loại các URL mà quy tắc không xác định được (~10–15% hàng).
  > Lấy key tại: [console.anthropic.com → API Keys](https://console.anthropic.com)
  > Nhập API key của bạn (dạng `sk-ant-...`):

  Khi nhận được → gọi `setup_api_key(api_key=...)`.
  - Thành công → "✓ API key đã lưu. Sẽ tự động dùng lại ở lần sau." → tiếp tục Question 1.
  - User bỏ qua → "Sẽ chỉ dùng rule-based (~85–90% URL). Có thể thêm key sau." → tiếp tục.

---

## Intake Dialog (hỏi từng câu, không hỏi cùng lúc)

### Question 1 — Nguồn dữ liệu

Hỏi user dữ liệu URL ở đâu. Chấp nhận:
- **Đường dẫn file** — Excel (.xlsx, .xls), CSV, TSV, JSON
- **Google Sheets URL** — link chia sẻ viewer
- **Dán trực tiếp** — user paste danh sách URL vào chat

### Question 2 — Domain website

Hỏi: "Domain của website là gì?" (ví dụ: `hacom.vn`, `thegioididong.com`)

Domain dùng để research trực tiếp cấu trúc website — không cần mô tả thủ công.

### Question 3 — Mục đích phân tích

Hỏi: "Bạn muốn phân tích gì?" Ví dụ:
- Nhóm trang nào đang nhận nhiều organic traffic nhất?
- So sánh hiệu quả giữa trang sản phẩm và blog?
- Phát hiện trang nội dung mỏng?

### Question 4 — Nhãn mẫu

Hỏi user cung cấp **3–10 nhãn mẫu** theo phong cách đặt tên của họ. Đây là input quan trọng nhất — xác định cấu trúc tên và làm few-shot examples.

Ví dụ (e-commerce tiếng Việt):
- "Trang chủ"
- "Danh mục - Máy giặt"
- "Sản phẩm - Máy giặt Toshiba 9kg"
- "Blog - Kiến thức"
- "Trang tĩnh - Liên hệ"

Nhắc user: nhãn mới sẽ theo đúng cấu trúc tên mẫu của họ.

### Question 5 — Đường dẫn output

Hỏi nơi lưu file Excel kết quả. Mặc định: `./labeled_output.xlsx`.

### Question 6 — Lưu ý (tùy chọn)

> 📝 **[6/6] Lưu ý thêm** _(tùy chọn — nhấn Enter để bỏ qua)_
> Có điều chỉnh đặc biệt nào không? Ví dụ:
> - "Bỏ qua các URL chứa /admin/ hoặc /test/"
> - "Tối đa 8 nhãn, không tạo thêm"
> - "Nhãn phải viết tiếng Anh"
> - "Sản phẩm điều hòa là ưu tiên cao nhất"
> - "Không gọi Claude API, chỉ dùng rule-based"

Nếu user bỏ qua (Enter / "không" / "skip"), set `notes = null`.

---

## Xác nhận

Sau khi thu thập đủ, trình bày tóm tắt:

```
📋 Tóm tắt
─────────────────────────────────────
API key:       ✓ Đã cấu hình  (hoặc "⚠ Chưa có — chỉ dùng rule-based")
Nguồn dữ liệu: [path/URL]
Domain:        [domain]
Mục đích:      [analysis goal]
Nhãn mẫu:     [label 1], [label 2], ...
Output:        [path]
Lưu ý:         [nội dung]  (hoặc —)
─────────────────────────────────────
Bắt đầu? (yes / chỉnh lại)
```

Chỉ tiếp tục sau khi user xác nhận.

---

## Áp dụng Lưu ý

Nếu `notes` không null, parse và áp dụng tại bước phù hợp:

| Loại lưu ý | Áp dụng khi | Cách áp dụng |
|---|---|---|
| Loại trừ URL pattern | Bước 1 — `load_data` | Báo user các URL này sẽ được gán `[excluded]` |
| Giới hạn số nhãn | Bước 2 — taxonomy | Xóa nhãn tần suất thấp nhất cho đến khi đủ |
| Ngôn ngữ nhãn | Bước 2 — taxonomy | Dịch/đổi tên tất cả nhãn gợi ý |
| Ưu tiên danh mục | Bước 2 — taxonomy | Đảm bảo có nhãn riêng cho danh mục đó |
| Chỉ rule-based | Bước 6 — batch | Bỏ qua hoàn toàn; ~10–15% sẽ là `[unclassified]` |
| Khác | Bước phù hợp nhất | Áp dụng nơi có hiệu quả cao nhất |

Sau khi áp dụng lưu ý tại mỗi bước, xác nhận ngắn: "✓ Đã áp dụng lưu ý: [nội dung]."

Nếu lưu ý mâu thuẫn với input khác (vd: "tối đa 5 nhãn" nhưng đã cung cấp 8 nhãn mẫu), hỏi user trước khi tiếp tục.

---

## Pipeline xử lý

### Bước 1 — Load dữ liệu

Gọi `load_data(source=...)`.

Báo cáo: tổng số hàng, 5–10 URL mẫu, cột được nhận dạng.

---

### Bước 2 — Research website (WebFetch)

Dùng `WebFetch` để research website thực tế trước khi xây taxonomy:

**2a. Fetch trang chủ** (`https://[domain]`):
- Trích xuất menu điều hướng chính → candidate category labels
- Ghi nhận cấu trúc breadcrumb nếu có

**2b. Fetch sitemap** (`https://[domain]/sitemap.xml`):
- Trích xuất URL patterns từ sitemap
- Nếu không tìm thấy → bỏ qua, tiếp tục

**2c. Spot-check 3–5 URL mẫu** (chọn URL phổ biến nhất trong dataset):
- Fetch từng URL, kiểm tra `<title>`, `<h1>`, breadcrumb, schema.org type
- Xác nhận loại trang: sản phẩm, danh mục, blog, v.v.

Tóm tắt:
```
🌐 Research website — hacom.vn
────────────────────────────────────
Menu: Laptop, PC, Màn hình, Linh kiện, Khuyến mãi, Tin tức

URL mẫu đã xác nhận:
  /laptop/macbook-pro-m3.html   → Sản phẩm (schema: Product)
  /laptop/                      → Danh mục  (schema: ItemList)
  /tin-tuc/review-laptop.html   → Blog
────────────────────────────────────
```

Nếu WebFetch bị chặn/timeout → ghi "Không thể truy cập", bỏ qua, không retry.

---

### Bước 3 — Xây dựng taxonomy

Gọi `build_label_taxonomy(seed_labels=[...], domain=..., analysis_goal=...)`.

Kết hợp 3 nguồn theo thứ tự ưu tiên:
1. **Nhãn mẫu của user** — match trước, suy ra cấu trúc tên
2. **Kết quả research website** — căn cứ vào cấu trúc thực của site
3. **Phân tích URL pattern** — lấp chỗ trống còn lại

Quy tắc:
- Tất cả nhãn mới theo đúng cấu trúc tên của nhãn mẫu
- Mỗi nhãn phải có ít nhất 1 URL pattern rule
- Tối đa 20 nhãn
- Không tạo nhãn trùng lặp (vd: "Sản phẩm" và "Trang sản phẩm" → gộp lại)

**Kiểm tra coverage trước khi trình bày:**

Apply tất cả rules lên toàn bộ dataset (không gọi API), tính % URL chưa được phân loại:
- Nếu "Chưa phân loại" > 10%: lấy 30 URL mẫu, phân tích pattern, tự động đề xuất thêm rules, hỏi user xác nhận trước khi tiếp tục
- Chỉ tiếp tục khi "Chưa phân loại" ≤ 10% (hoặc user chọn bỏ qua)

**DỪNG — trình bày taxonomy và chờ user xác nhận:**

```
📋 Đề xuất taxonomy — [N] nhãn
────────────────────────────────────────────────────────────
#   Nhãn                    Nguồn     Pattern          Ước tính
────────────────────────────────────────────────────────────
1   Trang chủ               Mẫu+W     root             0.1%
2   Danh mục - Laptop       W         /laptop/$        8%
3   Sản phẩm - Laptop       Mẫu+URL   /laptop/[slug]   4.2%
4   Blog - Tin tức           URL       /tin-tuc/        2.1%
...
    Chưa phân loại          —         —                8.2%
────────────────────────────────────────────────────────────
Nguồn: Mẫu=Seed | W=Website research | URL=URL analysis
```

Hỏi: "[S]ử dụng | [T]hêm nhãn | [X]óa nhãn | [Đ]ổi tên"

**Không gọi `save_label_config` cho đến khi user xác nhận.**

---

### Bước 4 — Lưu taxonomy

Gọi `save_label_config(session_id, labels=[...])` sau khi user xác nhận.

---

### Bước 5 — Rule-based classification

Gọi `apply_rule_based_labels(session_id)`:
- Dùng vectorized `Series.str.contains(regex=True)` — 0 API token
- Mỗi URL phải khớp đúng full pattern, không chỉ substring
- Quy tắc cụ thể hơn được áp dụng trước (priority order)

Báo cáo:
```
✓ Rule-based: 15,840 / 18,000 hàng (88%) — 0 token
  Sản phẩm chi tiết   9,200  (51%)
  Danh mục            3,100  (17%)
  Blog - Kiến thức      980   (5%)
  Còn lại (ambiguous): 2,160 hàng
```

**Sanity check:** Nếu bất kỳ nhãn nào chiếm > 40% tổng hàng:
```
⚠ "Sản phẩm chi tiết" chiếm 52% — cao hơn mức kỳ vọng.
  Xem 10 URL mẫu được gán nhãn này? (y/n)
```
Nếu user xác nhận rule quá rộng → quay về Bước 3 để điều chỉnh, rồi chạy lại.

---

### Bước 6 — Batch API (cho hàng ambiguous)

Yêu cầu API key. Nếu chưa có, hỏi:
> "Có thể xuất file với [X] hàng còn lại gán 'Chưa phân loại', hoặc nhập API key để phân loại tiếp."

Nếu tiếp tục với Batch API:

Gọi `submit_claude_batch(session_id)`:
- Prompt gửi đi phải bao gồm đúng danh sách nhãn đã duyệt
- Chỉ được chọn từ danh sách nhãn; không tạo nhãn mới
- Model: Haiku

**DỪNG — trình bày lựa chọn polling, không gọi tool nào cho đến khi user trả lời:**

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

**[A] Auto:** Sau đúng khoảng thời gian đã chọn, gọi `poll_batch_status` **đúng 1 lần**. Nếu chưa xong → hỏi chờ thêm hay chuyển thủ công. Không bao giờ poll nhiều hơn 1 lần trong cùng 1 lượt.

**[B] Thủ công:** Lưu session_id, chờ user báo "batch xong rồi" → gọi `poll_batch_status` **đúng 1 lần** để xác nhận. Nếu chưa xong → thông báo và đợi tiếp.

---

### Bước 7 — Merge kết quả

Gọi `merge_batch_results(session_id)` chỉ khi `all_ended: true`:
- Stream qua iterator — không load toàn bộ vào list
- Mọi nhãn trả về không nằm trong taxonomy → thay bằng `"Chưa phân loại"`
- Báo cáo: succeeded, replaced (nhãn ngoài taxonomy), failed, skipped

---

### Bước 8 — Validation mẫu ngẫu nhiên

Chạy sau merge, trước khi export. Bỏ qua nếu không có API key.

Với mỗi nhãn có ≥ 50 hàng, lấy ngẫu nhiên 10 URL đã được rule gán nhãn, gửi cho Claude xác nhận (gọi trực tiếp, không dùng Batch API):

| Sai sót | Hành động |
|---|---|
| < 10% sai trong 1 nhóm | ✓ Chấp nhận |
| 10–30% sai | ⚠ Cảnh báo, hỏi có muốn fix rule không |
| > 30% sai | 🔴 Dừng export — cần sửa rule |

Nếu user chọn fix: đề xuất rule mới, gọi lại `apply_rule_based_labels` chỉ cho nhóm bị lỗi, test lại cho đến khi < 10%.

Báo cáo:
```
🧪 Kiểm tra độ chính xác (10 mẫu/nhãn)
──────────────────────────────────────────────
Nhãn                  URLs    Đúng  Sai  Status
──────────────────────────────────────────────
Sản phẩm - Laptop     1,334    9     1   ✓ 90%
Danh mục - Laptop       383    8     2   ✓ 80%
Blog - Tin tức          349   10     0   ✓ 100%
Chưa phân loại          854    —     —   ℹ 8.2%
──────────────────────────────────────────────
```

---

### Bước 9 — Kiểm tra bất thường trước export

Không gọi `export_to_excel` cho đến khi bước này qua.

```
🔎 Kiểm tra bất thường
──────────────────────────────────────────────────────
Phân bổ nhãn:
  Sản phẩm chi tiết    9,200  (51%)   ⚠ Vượt 40%
  Danh mục             3,100  (17%)   ✓
  Blog - Kiến thức       980   (5%)   ✓
  Chưa phân loại       3,380  (18%)   ℹ Xem xét thêm rules

Độ tin cậy:
  Avg confidence (rule):  0.94  ✓
  Avg confidence (batch): 0.81  ✓
  Rows confidence < 0.6:   420  ⚠ Nên review

Tính toàn vẹn:
  Nhãn ngoài taxonomy:  0  ✓
  URL trùng lặp:        0  ✓
  URL thiếu nhãn:       0  ✓
──────────────────────────────────────────────────────
Tiến hành xuất file? [Y] Xuất / [R] Review nhãn nghi vấn trước
```

Ngưỡng cảnh báo:
- Nhãn > 40% → cảnh báo, xem 10 mẫu, để user quyết định
- "Chưa phân loại" > 10% → lấy 20 URL mẫu, phân tích pattern, đề xuất thêm rules trước khi export
- Confidence < 0.6 > 5% → cảnh báo, đề nghị gửi thêm lên Batch API
- Nhãn ngoài taxonomy → hard block, sửa trước khi export

---

### Bước 10 — Export

Gọi `export_to_excel(session_id, output_path)`:
- Cột: `url`, `label`, `confidence`, `method` (`rule` / `batch` / `fallback`)
- Báo cáo kích thước file và tổng số hàng

---

### Bước 11 — Phân phối và review

Gọi `get_label_distribution(session_id)`:

```
📊 Kết quả phân loại
──────────────────────────────────────────
Nhãn                    Count    %    Conf
──────────────────────────────────────────
Sản phẩm chi tiết       8,450   68%   0.91
Blog - Kiến thức        1,890   15%   0.87
Danh mục - Máy giặt       980    8%   0.94
Chưa phân loại            220    2%   —
──────────────────────────────────────────
```

Hỏi: "Muốn xem và sửa các URL có độ tin cậy thấp không? (y/n)"

Nếu có → gọi `get_low_confidence_samples` (tối đa 50 hàng) → user xem xét → gọi `apply_corrections` nếu có chỉnh sửa → re-export.

---

## Kết quả cuối cùng

```
✅ Hoàn tất — ./labeled_output.xlsx
   Rule-based:     15,840 hàng  (88%)
   Batch API:       2,100 hàng  (12%)
   Chưa phân loại:   220 hàng
   Session ID: [id]  (dùng để tiếp tục nếu cần)
```

---

## Resume

Nếu user nói "resume session [session_id]" hoặc "batch xong rồi", bỏ qua intake dialog và gọi thẳng `poll_batch_status` hoặc `merge_batch_results` với session_id đã lưu.

---

## Token Budget

Không hiển thị raw data rows trong conversation. Chỉ trả về: row counts, tên nhãn, confidence scores, và mẫu nhỏ (≤ 10 hàng để xác nhận load, ≤ 50 hàng để review).
