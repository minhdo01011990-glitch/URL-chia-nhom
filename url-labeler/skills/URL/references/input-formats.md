# Input Format Reference

This file documents how `load_data` should handle each supported input format.
Pass `source_format` explicitly to avoid ambiguity.

---

## Supported Formats

### Excel (.xlsx, .xls)

- **source_format**: `excel`
- **Parser**: `openpyxl.load_workbook(read_only=True, data_only=True)` — never `pd.read_excel()` (OOM risk on large files)
- **Column detection**: Auto-detect column named "url", "URL", "link", "Link", "address". If ambiguous, show first 3 column names and ask user to confirm.
- **Sheet**: Default to first sheet. If multiple sheets, ask user which one.

### CSV / TSV

- **source_format**: `csv` or `tsv`
- **Parser**: `pd.read_csv(chunksize=10_000)` — chunked to avoid OOM
- **Delimiter**: Auto-detect comma vs tab. If mixed or unclear, ask user.
- **Encoding**: Try UTF-8 first, fallback to UTF-8-BOM, then latin-1.

### JSON

- **source_format**: `json`
- **Accepted structures**:
  - Array of URL strings: `["https://...", "https://..."]`
  - Array of objects: `[{"url": "...", "title": "..."}, ...]`
  - Object with a URLs array key: `{"urls": [...], "meta": {...}}`
- **Column detection**: If objects, look for key named `url`, `URL`, `link`, `href`. If not found, list top-level keys and ask user.

### Google Sheets

- **source_format**: `google_sheets`
- **Parser**: `gspread_dataframe.get_as_dataframe(evaluate_formulas=False)` — single batch API call
- **Auth**: Requires `GOOGLE_SERVICE_ACCOUNT_JSON` env var (path to key file or raw JSON string)
- **URL extraction**: From share link, extract spreadsheet ID and use default first sheet unless user specifies.

### NotebookLM Export (.md, .txt)

- **source_format**: `notebooklm`
- **How it works**: NotebookLM can export sources and content as markdown or plain text. URLs typically appear as:
  - Markdown links: `[text](https://...)`
  - Plain URLs in lists: `- https://...` or `* https://...`
  - Table rows with a URL column
  - Footnotes/citations: `[1]: https://...`
- **Parser logic**:
  1. Extract all strings matching `https?://[^\s\)\]"']+`
  2. Deduplicate while preserving order
  3. Optionally extract anchor text as a "title" column
  4. Show user count of URLs found and first 10 for confirmation
- **Limitation**: NotebookLM audio overviews cannot be parsed — inform user if they upload an audio file.

### Paste / Clipboard (inline URLs)

- **source_format**: `paste`
- **Trigger**: User pastes text directly in chat without a file
- **Parser**: Same regex as NotebookLM — extract all `https?://` URLs from pasted text
- **Minimum**: At least 1 URL required to proceed

---

## Format Auto-Detection

If `source_format` is not specified, detect by:

1. File extension: `.xlsx/.xls` → excel, `.csv` → csv, `.tsv` → tsv, `.json` → json, `.md/.txt` → notebooklm
2. URL prefix `https://docs.google.com/spreadsheets/` → google_sheets
3. No file (inline text) → paste

When detection is ambiguous, ask the user before loading.

---

## Large File Handling

| Row count | Strategy |
|-----------|----------|
| < 10,000 | Load fully into memory |
| 10,000 – 75,000 | Chunk reading (CSV), read_only workbook (Excel) |
| > 75,000 | Warn user; offer to process a sample first |

Always report: total rows loaded, column detected as URL source, and any rows skipped (empty, malformed).
