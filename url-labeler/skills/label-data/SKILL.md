---
name: label-data
description: >
  This skill should be used when the user wants to "apply labels to URLs",
  "run the classifier", "gán nhãn dữ liệu", "chạy phân loại URL",
  "label my data", "submit to batch API", "tiếp tục đánh nhãn", "kiểm tra
  batch đã xong chưa", or run Step 2 of the URL labeling pipeline. Also use
  when the user wants to check batch status, resume a pending batch, or
  export results without running the full pipeline again.
metadata:
  version: "0.3.0"
---

# Label Data — Standalone Step

This skill runs Step 2 of the URL labeling pipeline. The classification strategy is: **rule-based first (0 tokens), Batch API only for genuinely ambiguous rows**. Rules must be precise — not broad catch-alls.

---

## HARD CONSTRAINT — label lock

**Only labels from the saved taxonomy may appear in the output.** Never create, suggest, or allow new labels during classification — not in rule matching, not in Batch API prompts, not in fallback logic. If a URL fits no label → assign `"Chưa phân loại"`. This constraint must be enforced at every step.

---

## Prerequisites

Ask the user for their **session ID** from `build-labels`. Do not ask for seed labels, website description, or taxonomy inputs — they are already saved in the session.

If the user has no session ID → direct to `/url-labeler:build-labels` first.

**Inputs to collect:**
1. Session ID (UUID from the `build-labels` step)
2. Output path (default: `./labeled_output.xlsx`)

---

## Step 2a — Verify taxonomy

Call `get_label_distribution_tool(session_id, stage="config")` to load and display the saved taxonomy:

```
📋 Taxonomy loaded — session abc123-def456
──────────────────────────────────────────
  1. Trang chủ
  2. Danh mục - Máy giặt
  3. Sản phẩm chi tiết
  4. Blog - Kiến thức
  5. Trang tĩnh - Liên hệ
──────────────────────────────────────────
5 nhãn | 18,000 URL cần phân loại
```

If session or config not found → stop, show error, direct user to rebuild taxonomy. Do not proceed.

---

## Step 2b — URL structure analysis (before rules run)

Before calling the classifier, call `load_data(session_id, analyze_structure=True)` to extract URL structure statistics. Use this output to **audit and tighten the rule patterns** before classification runs.

Display a structure summary to the user:

```
🔍 Phân tích cấu trúc URL
──────────────────────────────────────────────────
Độ sâu path phổ biến:
  /slug/              →  1,200 URLs  (6.7%)   → thường là Danh mục
  /slug/slug/         →  9,800 URLs  (54%)    → thường là Sản phẩm
  /slug/slug/slug/    →  3,400 URLs  (18.9%)  → Sản phẩm hoặc Blog

Top keywords trong path:
  "may-giat"          →  2,100 URLs
  "tin-tuc"           →    980 URLs
  "khuyen-mai"        →    430 URLs
  "san-pham"          →  5,200 URLs  ← rủi ro: keyword quá rộng

Rules hiện tại — cảnh báo:
  ⚠ "Sản phẩm chi tiết" khớp 54% URL — có thể quá rộng
  ✓ "Blog - Kiến thức"  khớp 5.4% URL — hợp lý
──────────────────────────────────────────────────
```

**Rules are too broad if a single label would capture > 40% of all rows.** If this is detected, do not proceed to classification — instead:
1. Show which rule is causing the over-capture with example URLs
2. Suggest narrowing options:
   - Add a more specific path pattern (e.g., `/san-pham/[^/]+/[^/]+` instead of `/san-pham/`)
   - Require minimum path depth (e.g., depth ≥ 3 for products)
   - Exclude sub-paths that belong to another label
3. Ask the user to confirm the narrowed rules before continuing

**Rules must match based on specificity priority** — longer, more specific path patterns take precedence over shorter ones. The classifier must apply rules in order from most specific to least specific.

---

## Step 2c — Rule-based classification

Call `apply_rule_based_labels_tool(session_id)` after the structure analysis confirms rules are acceptable:

- Uses vectorized `Series.str.contains(regex=True)` with specificity ordering — 0 API tokens
- A URL must match the rule's **full pattern** (path structure + keyword), not just a substring
- Report: rows labeled per label, rows remaining (ambiguous), coverage %

```
✓ Rule-based: 15,840 / 18,000 hàng (88%) — 0 token
  Phân bổ:
    Sản phẩm chi tiết   9,200  (52%)
    Danh mục            3,100  (17%)
    Blog - Kiến thức      980   (5%)
    Trang chủ              60   (0.3%)
    Trang tĩnh            500   (2.8%)
  Còn lại (ambiguous): 2,160 hàng
```

**Post-rule sanity check:** If any single label captured > 40% of total rows after classification, flag it before continuing:

```
⚠ Cảnh báo: "Sản phẩm chi tiết" đang chiếm 52% — cao hơn mức kỳ vọng.
  Xem 10 URL mẫu được gán nhãn này?  (y/n)
```

Show 10 sample URLs. If the user confirms the label is too broad → pause, return to step 2b to tighten the rule, then re-run classification.

---

## Step 2d — Batch API for ambiguous rows (requires API key)

Rule-based takes priority. Batch API is only for rows that genuinely matched no rule.

**API key check:** Call `check_api_key()` before submitting. If not configured, offer:
> "Có thể xuất file ngay với 2,160 hàng còn lại gán nhãn 'Chưa phân loại', hoặc nhập API key để phân loại tiếp."

If user proceeds with Batch API:

1. Call `submit_claude_batch_tool(session_id)`:
   - The batch prompt must include the **exact list of approved labels** from the saved taxonomy
   - The prompt must explicitly state: "Chỉ được chọn từ danh sách nhãn sau. Không được tạo nhãn mới."
   - Include 2–3 few-shot examples per label using real URLs from the rule-classified set
   - Model: Haiku

2. After submitting, **STOP and present polling options** — do NOT call any tool until user responds:

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

   **Nếu chọn [A] — Auto:**
   - User chọn khoảng thời gian → Claude xác nhận: "✓ Sẽ kiểm tra lại sau [X] phút. Bạn không cần làm gì."
   - **KHÔNG gọi bất kỳ tool nào trong khoảng chờ đó.**
   - Sau đúng khoảng thời gian đã hẹn (user quay lại hoặc session tiếp tục), gọi `poll_batch_status_tool(session_id)` **đúng 1 lần**.
   - Nếu `all_ended: true` → chuyển sang bước merge (bước 3).
   - Nếu chưa xong → hiện tiến độ + hỏi: "Chờ thêm [X] phút nữa? (hoặc đổi sang chế độ thủ công)"
   - **Không bao giờ gọi `poll_batch_status_tool` quá 1 lần trong cùng một lượt trả lời.**

   **Nếu chọn [B] — Thủ công:**
   - Xác nhận: "✓ Session đã lưu. Khi Batch API hoàn tất, nhắn 'batch xong rồi' để tiếp tục."
   - Khi user báo xong → gọi `poll_batch_status_tool(session_id)` **đúng 1 lần** để xác nhận `all_ended: true`.
   - Nếu chưa xong → thông báo: "Batch chưa hoàn tất ([X]/[Y] succeeded). Chờ thêm rồi báo lại."
   - Nếu đã xong → chuyển sang bước merge.

3. On batch `ended`: call `merge_batch_results_tool(session_id, batch_id)`:
   - Stream via iterator — never collect all into a list
   - **After merging: validate that every returned label exists in the saved taxonomy.** Any label not in the taxonomy → replace with `"Chưa phân loại"` and log as a warning
   - Report: succeeded, replaced (invalid label), failed, skipped

### Batch API error handling

| Error | Action |
|---|---|
| Batch expired (> 24h) | Inform user; offer resubmit or export partial with "Chưa phân loại" |
| Partial failure | Merge succeeded rows; failed rows → "Chưa phân loại" |
| API quota exceeded | Pause; suggest retry in 1 hour; session is preserved |
| Network timeout during poll | Retry next poll; do not restart batch |
| Label not in taxonomy (hallucinated) | Replace with "Chưa phân loại"; log count of replacements |

---

## Step 2d-bis — Random sample validation với Claude API

**Chạy sau khi merge batch results xong, trước khi export.** Nếu không có API key, bỏ qua bước này.

### Mục đích
Phát hiện rule gán nhãn sai hệ thống trước khi xuất file — đặc biệt với nhóm có số lượng lớn.

### Cách chạy

Với mỗi nhãn có ≥ 50 hàng, lấy ngẫu nhiên **10 URL** (ưu tiên các nhãn coverage cao):

```
Gọi `get_low_confidence_samples_tool` hoặc random sample từ mỗi label group
→ Gửi batch nhỏ cho Claude (không dùng Batch API — gọi trực tiếp để có kết quả ngay)
→ Prompt: "Với mỗi URL sau, nhãn đã gán có đúng không? Taxonomy: [danh sách nhãn]"
```

### Xử lý kết quả

| Sai sót phát hiện | Hành động |
|---|---|
| < 10% sai trong 1 nhóm | ✓ Chấp nhận, ghi note vào file output |
| 10–30% sai | ⚠ Cảnh báo user, hỏi có muốn fix rule và re-label nhóm đó không |
| > 30% sai | 🔴 Dừng export — rule cần sửa lại |

**Nếu user chọn fix rule:**
1. Hiển thị các URL bị sai và pattern chung
2. Đề xuất rule mới
3. Gọi `apply_rule_based_labels_tool` lại CHỈ cho nhóm bị lỗi (không chạy lại toàn bộ)
4. Test lại 10 mẫu mới cho nhóm vừa fix
5. Lặp cho đến khi sai sót < 10% hoặc user bỏ qua

Hiển thị báo cáo validation trước khi chuyển sang anomaly check:

```
🧪 Random sample validation (10 mẫu/nhóm)
──────────────────────────────────────────────────────────
Nhãn                      URLs    Sample  Đúng  Sai  Status
──────────────────────────────────────────────────────────
Sản phẩm - linh kiện PC  1,334     10      9     1   ✓ 90%
Sản phẩm - Gaming gear     383     10      8     2   ✓ 80%
Sản phẩm - màn hình        349     10     10     0   ✓ 100%
Sản phẩm - TB văn phòng    232     10      7     3   ✓ 70%
Khác (chưa phân loại)      854     —       —     —   ℹ 19.5%
──────────────────────────────────────────────────────────
Avg accuracy: 85% | Nhóm cần xem lại: 0
```

## Step 2e — Pre-export anomaly check

**Do not call `export_to_excel_tool` until this step passes.**

Run the following checks on the merged results. Show a report and ask for user confirmation:

```
🔎 Kiểm tra bất thường trước khi xuất
──────────────────────────────────────────────────────
Phân bổ nhãn:
  Sản phẩm chi tiết    9,200  (51%)   ⚠ Vượt 40% — xem xét lại
  Danh mục             3,100  (17%)   ✓
  Blog - Kiến thức       980   (5%)   ✓
  Trang chủ               60   (0.3%) ✓
  Trang tĩnh             500   (2.8%) ✓
  Chưa phân loại       3,380  (18%)   ℹ Chưa phân loại (batch không đủ)

Kiểm tra độ tin cậy:
  Avg confidence (rule):  0.94  ✓
  Avg confidence (batch): 0.81  ✓
  Rows confidence < 0.6:   420  ⚠ Nên review thủ công

Kiểm tra tính toàn vẹn:
  Nhãn ngoài taxonomy:     0   ✓
  URL trùng lặp:           0   ✓
  URL thiếu nhãn:          0   ✓
──────────────────────────────────────────────────────
Tiến hành xuất file? [Y] Xuất / [R] Review nhãn nghi vấn trước
```

**Anomaly thresholds:**
- Any label > 40% of rows → warn, show 10 samples, let user decide
- More than 10% rows as "Chưa phân loại" → warn + lấy 20 URL mẫu từ nhóm này → phân tích pattern → đề xuất thêm rules mới để giảm nhóm Khác trước khi export
- More than 5% rows with confidence < 0.6 → warn, offer to send those rows to Batch API
- Any label in results not in taxonomy → hard block, fix before export

Only proceed to export after user selects [Y].

---

## Step 2f — Export

Call `export_to_excel_tool(session_id, output_path)`:
- Columns: `url`, `label`, `confidence`, `method` (`rule` / `batch` / `fallback`)
- Report file size and total row count

## Final summary

```
✅ Đánh nhãn hoàn tất
   Rule-based:        15,840 hàng  (88%)
   Batch API:          2,100 hàng  (12%)
   Chưa phân loại:       220 hàng
   File: ./labeled_output.xlsx
```

Offer to run `/url-labeler:review-labels` to inspect and correct results.
