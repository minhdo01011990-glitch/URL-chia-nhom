# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

`url-labeler` is a Claude Code plugin that labels website URLs by content type (homepage, category, product, blog...) for SEO organic traffic analysis. It handles up to 75,000 rows via rule-based classification first, then Claude Batch API for ambiguous cases.

## Development Commands

```bash
# Install dependencies
pip install -e ".[dev]"

# Run MCP server locally (for testing plugin tools)
url-labeler-server

# Test the plugin in Claude Code
claude --plugin-dir .

# Run all tests
python -m pytest tests/

# Run a single test file
python -m pytest tests/test_classifier.py -v

# Reload plugin without restarting Claude Code (run inside Claude Code)
/reload-plugins
```

## Architecture

The plugin has two distinct layers that must be understood together:

### Layer 1 — Claude Code Plugin (user-facing)

Skills in `skills/` define slash commands. The main entry point is `/url-labeler:URL`, which activates the `label-coordinator` agent. The agent conducts a **5-question intake dialog** before calling any MCP tools:

1. **Data source** — file path or Google Sheets URL
2. **Website description** — products/services, used as context for taxonomy building
3. **Analysis goal** — what to analyze, shapes label suggestions
4. **Seed labels** — 3–10 example labels the user provides in their preferred naming style (e.g. "Danh mục - Máy giặt", "Blog - Kiến thức"). These are the most important input: they define the label naming structure and act as few-shot examples for the AI.
5. **Output path** — defaults to `./labeled_output.xlsx`

Only after the user confirms the summary does processing begin.

Other skills (`build-labels`, `label-data`, `review-labels`) are standalone entry points for running individual steps of the pipeline.

### Layer 2 — MCP Server (compute layer)

`src/server.py` exposes 11 tools via `fastmcp`. All heavy computation happens here — Claude Code never sees the raw data rows. What Claude receives is only summaries, label suggestions, and statistics (< 5,000 tokens total for a full pipeline run).

The 11 MCP tools map to four modules:
- `src/tools/io_tools.py` — `load_data`, `export_to_excel`
- `src/tools/label_tools.py` — `build_label_taxonomy`, `save_label_config`, `apply_rule_based_labels`
- `src/tools/batch_tools.py` — `submit_claude_batch`, `poll_batch_status`, `merge_batch_results`
- `src/tools/review_tools.py` — `get_label_distribution`, `get_low_confidence_samples`, `apply_corrections`

### Core Processing Pipeline

```
load_data → build_label_taxonomy(seed_labels=[...]) → [user review] → save_label_config
         → apply_rule_based_labels (~85-90% of rows, 0 tokens)
         → submit_claude_batch (remaining ~10-15%, Haiku model, Batch API)
         → poll_batch_status → merge_batch_results
         → export_to_excel → get_label_distribution → [user review/corrections]
```

Sessions are identified by a `session_id` (UUID). All intermediate state is stored in `~/.url-labeler/{session_id}/` as Parquet files, enabling resume after interruption.

## Key Implementation Constraints

### Data loading — never use `pd.read_excel()` directly
For Excel files, always use `openpyxl.load_workbook(read_only=True, data_only=True)` — `pd.read_excel()` loads the full DOM into RAM (~1.5GB for large files). For CSV, use `pd.read_csv(chunksize=10_000)` to avoid OOM. For Google Sheets, `gspread_dataframe.get_as_dataframe(evaluate_formulas=False)` makes a single batch API call.

### Taxonomy builder — seed labels drive everything
The `build_label_taxonomy` tool receives the user's example labels as `seed_labels`. The builder must: (1) match URL clusters to seed labels first before creating new ones, (2) infer naming structure from seeds and apply it to new labels, (3) pass seeds as few-shot examples in the optional Claude API call. New labels not derivable from the seed style should not be created.

### Classifier — use vectorized pandas, not `df.apply()`
`src/core/classifier.py` uses `Series.str.contains(regex=True)` with boolean masks in priority order. `df.apply(lambda row: ...)` is ~50x slower and will not meet the < 2 second target for 75k rows.

### Parquet for checkpoints, Excel only for final output
Intermediate results are stored as `.parquet` (gzip). Benchmark: Parquet read/write is ~7x faster and ~4x smaller than CSV at this row count. Excel is only written at the end via `pd.ExcelWriter`.

### Claude Batch API — streaming results, not batch download
When merging batch results, iterate `client.beta.messages.batches.results(batch_id)` as a streaming iterator. Do not collect all results into a list first — this avoids loading up to 100k result objects into RAM simultaneously.

### Token budget — keep Claude Code context minimal
MCP tool return values must never include raw data rows. Return only: row counts, label names, confidence scores, and small samples (≤ 10 rows for load confirmation, ≤ 50 rows for review). The full pipeline should consume < 5,000 tokens in Claude Code context.

## Environment Variables

| Variable | Required | Purpose |
|---|---|---|
| `ANTHROPIC_API_KEY` | Yes | Claude API access (Batch API + taxonomy building) |
| `GOOGLE_SERVICE_ACCOUNT_JSON` | Only for Google Sheets | Path to service account key file, or JSON string |

## Plugin Entry Points

| Skill | Command | Purpose |
|---|---|---|
| `URL` | `/url-labeler:URL` | Full pipeline with guided intake dialog (recommended) |
| `build-labels` | `/url-labeler:build-labels` | Step 1 only — build label taxonomy |
| `label-data` | `/url-labeler:label-data` | Step 2 only — apply labels |
| `review-labels` | `/url-labeler:review-labels` | Step 3 only — review and correct |

## Distribution

The plugin is packaged with `hatchling`. Pushing a `v*` tag triggers `.github/workflows/publish.yml` to publish to PyPI. Users install with `pip install url-labeler` and add `.mcp.json` to their project.
