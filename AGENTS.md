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
2. **Require constant maintenance** — Every new analysis requirement means editing the template,
   defeating the purpose of automation.
3. **Violate the dynamic design** — The report generation must adapt to whatever the agent produces,
   parsing the actual Markdown content at runtime.

### Correct Approach

The Agent should:
1. **Read the `.txt` file** and parse its actual content (tables, lists, image descriptions, paragraphs).
2. **Dynamically decide** what kind of visualization (table, bar chart, doughnut, line chart) fits each section.
3. **Generate a throw-away Python script** tailored to the *current* `.txt` content,
   execute it to produce `temp_report.html`, then export PDF via Playwright.
4. **Clean up** the temporary script and HTML after PDF generation.
5. **Ensure human-readable numeric axes** — When chart values exceed 5-figure magnitudes (e.g. >= 500,000), rescale axes and annotate units (e.g. 'k', 'M') so labels remain compact and professional. Never leave raw unscaled numbers on axis ticks.

This ensures the workflow works for **any** sales analysis output,
not just the ones that match a pre-defined template.
