# Environment Notes for Agent

## Playwright / Chromium
- Playwright **v1.62.0** is already installed in the active conda env `sales_assistant`.
- Chromium browser binary is already installed via `playwright install chromium`.
- **DO NOT** run `playwright install chromium` again. It is redundant and wastes time.
- The Python executable available in this workspace uses the `sales_assistant` conda env.

## PDF Generation Workflow
- When generating PDFs from HTML, use the already-installed Playwright directly.
- No browser-installation preflight is required.

## File Writing Best Practice
- When writing multi-line scripts or HTML files, **use `apply_patch`** instead of passing
  multi-line strings through PowerShell `-Command`. PowerShell interprets special characters
  (e.g. `&`, `<`, `>`, `$`) differently and can corrupt file content.
- `apply_patch` is the intended Codex CLI tool for file modifications — it writes content
  directly without shell escaping issues.

## Why We Do NOT Generate a Fixed `generate_report.py` Template

The `.txt` file produced by `run.py` is **not guaranteed to have a fixed structure**.
Every execution may contain different analyses, different sections, different tables,
and different chart descriptions depending on the user query and the data.

Because of this variability, a hard-coded `generate_report.py` would:
1. **Fail on new content** — If a new section contains an analysis the template does not handle
   (e.g. a time-series line chart, a scatter plot, or a completely new metric), the script breaks.
2. **Require constant maintenance** — Every new analysis requirement means editing the template,   defeating the purpose of automation.
3. **Violate the dynamic design** — The report generation must adapt to whatever the agent produces,
   parsing the actual Markdown content at runtime.

### Correct Approach

The Agent should:
1. **Read the `.txt` file** and parse its actual content (tables, lists, image descriptions, paragraphs).
2. **Dynamically decide** what kind of visualization (table, bar chart, doughnut, line chart) fits each section.
3. **Generate a throw-away Python script** tailored to the *current* `.txt` content,
   execute it to produce `temp_report.html`, then export PDF via Playwright.
4. **Clean up** the temporary script and HTML after PDF generation.
5. **Ensure human-readable numeric axes** — When chart values exceed 5-figure magnitudes (e.g. >= 500,000), rescale axes and annotate units (e.g. `'k'`, `'M'`) so labels remain compact and professional. Never leave raw unscaled numbers on axis ticks.

This ensures the workflow works for **any** sales analysis output,
not just the ones that match a pre-defined template.

## Portable Embedded-Python `setup.bat` Pattern

When the user asks for a `setup.bat` that installs Python dependencies, **always use the embedded-Python approach** (download the official `python-3.14.7-embed-amd64.zip`, enable pip, install dependencies from `requirements.txt`). Do NOT assume the user already has a system Python or conda env.

### Key Principles

- **Idempotent**: Skip download if `python\python.exe` already exists.
- **Self-contained**: Everything lives in the repo folder (`python/`).
- **Portable**: Use `%~dp0` and `cd /d "%~dp0"` so the batch works regardless of where the folder is placed.
- **Explicit version**: Match the project`'s Python version (currently **3.14.7**). Update the embed zip URL and the `._pth` filename (`python314._pth`) if the version changes.
- **Chromium**: After `pip install`, run `python\python.exe -m playwright install chromium`.

### Prompt Description (English)

> Create a Windows `setup.bat` that downloads and unpacks the embedded Python 3.14.7 zip into a local `python/` folder, enables pip by writing `python314._pth`, installs `get-pip.py`, then installs dependencies from `requirements.txt` and runs `playwright install chromium`. It should be idempotent (skip download if `python\python.exe` already exists) and use `%~dp0` so it works regardless of where the folder is placed.

### Prompt Description (Chinese)

> 我要一個 Windows 用的 `setup.bat`，用 embedded Python 的方式，讓沒裝 Python 的人也能直接跑。流程：檢查是否已有 `python\python.exe` → 沒有就下載 Python 3.14.7 embedded zip → 解壓 → 啟用 pip → 裝 `requirements.txt` → 裝 Playwright Chromium。要能用 `%~dp0` 保持路徑正確，且重複執行不會重複下載。

### Reference Implementation

See `setup.bat` in this repo for the canonical implementation.

### Known Pitfall: Writing `python314._pth` with Newlines

Embedded Python requires a `.pth` file with proper line breaks:

```
python314.zip
.

import site
```

**NEVER** use `Set-Content -Value "python314.zip\n.\n\nimport site"` from PowerShell (or a batch calling PowerShell with that string), because `\n` will be written as literal characters instead of actual newlines. This causes a fatal `ModuleNotFoundError: No module named 'encodings'`.

**Correct approach** in a batch file:

```batch
powershell -NoProfile -ExecutionPolicy Bypass -Command "[System.IO.File]::WriteAllLines('python\python314._pth', @('python314.zip', '.', '', 'import site'), [System.Text.Encoding]::ASCII)"
```

This uses the .NET `WriteAllLines` method, which handles actual line breaks correctly and produces a valid `.pth` file.
