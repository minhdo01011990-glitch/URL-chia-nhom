# url-labeler

A Cowork plugin that classifies website URLs by content type (homepage, category, product, blog...) for SEO organic traffic analysis. Handles up to **75,000 rows** via fast rule-based classification (~85–90% of rows, 0 tokens) followed by Claude Batch API for ambiguous cases.

---

## Installation

### Step 1 — Install MCP server (terminal)

```bash
pip install url-labeler
url-labeler-install
```

`url-labeler-install` registers the MCP server in both Claude Desktop App and Claude Code automatically.

**After running:**

| Environment | Next step |
|---|---|
| Claude Desktop App | Quit completely (Cmd+Q on Mac) then reopen — 🔧 icon = success |
| Claude Code | Works immediately, no restart needed |

### Step 2 — Install plugin (manual)

1. Download **`url-labeler.plugin`** from [Releases](https://github.com/minhdo01011990-glitch/URL-chia-nhom/releases/latest)
2. Open Claude → **Settings → Plugins → Upload file**
3. Select the downloaded file → confirm

---

## Skills

| Skill | Command | Purpose |
|---|---|---|
| `URL` | `/url-labeler:URL` | Full guided pipeline — recommended entry point |
| `build-labels` | `/url-labeler:build-labels` | Step 1 only — build label taxonomy |
| `label-data` | `/url-labeler:label-data` | Step 2 only — apply labels |
| `review-labels` | `/url-labeler:review-labels` | Step 3 only — review and correct |

---

## Supported Input Formats

| Format | Description |
|---|---|
| Excel (.xlsx, .xls) | Reads with openpyxl in read-only mode (memory-safe) |
| CSV / TSV | Chunked reading, auto-detects delimiter and encoding |
| JSON | Supports arrays of URLs or objects with a URL field |
| Google Sheets | Single batch API call via gspread |
| **NotebookLM export** | Extracts URLs from .md/.txt exports (lists, tables, footnotes, links) |
| Paste / clipboard | Extracts URLs from text pasted directly in chat |

---

## Setup

### Required

Set your Anthropic API key in your environment:

```bash
export ANTHROPIC_API_KEY=sk-ant-...
```

### For Google Sheets (optional)

Create a Google service account and share the sheet with it. Then set:

```bash
# Either a path to the key file:
export GOOGLE_SERVICE_ACCOUNT_JSON=/path/to/key.json

# Or the raw JSON string:
export GOOGLE_SERVICE_ACCOUNT_JSON='{"type":"service_account",...}'
```

---

## Usage

### Full pipeline (recommended)

Type `/url-labeler:URL` — Claude will guide you through a dialog:

1. Data source (file path, Google Sheets URL, or paste)
2. Brand name and domain
3. Analysis goal
4. Seed labels (3–10 examples in your naming style)

### Step-by-step

Run each step independently when you need more control:

```
/url-labeler:build-labels   → design your label taxonomy
/url-labeler:label-data     → apply labels to data
/url-labeler:review-labels  → inspect and correct results
```

### Resume interrupted runs

Sessions are saved to `~/.url-labeler/{session_id}/` as Parquet files. If interrupted, run `/url-labeler:URL` and say "resume session abc123" to pick up where you left off.

---

## How it works

```
load_data → build_label_taxonomy → save_label_config
          → apply_rule_based_labels  (~85-90% of rows, instant)
          → submit_claude_batch      (remaining ~10-15%, Haiku model)
          → poll_batch_status → merge_batch_results
          → export_to_excel → get_label_distribution
```

The final output is an Excel file with columns: `url`, `label`, `confidence`, `method` (rule / batch).

---

## MCP Tools Reference

The plugin exposes 11 tools via the `url-labeler` MCP server:

| Tool | Purpose |
|---|---|
| `load_data` | Load URLs from any supported format |
| `build_label_taxonomy` | Generate taxonomy from seed labels |
| `save_label_config` | Persist taxonomy to session |
| `apply_rule_based_labels` | Fast vectorized classification |
| `submit_claude_batch` | Submit ambiguous rows to Batch API |
| `poll_batch_status` | Check batch completion |
| `merge_batch_results` | Stream and merge batch results |
| `export_to_excel` | Write final labeled output |
| `get_label_distribution` | Summary statistics by label |
| `get_low_confidence_samples` | Sample rows for manual review |
| `apply_corrections` | Apply manual label corrections |
