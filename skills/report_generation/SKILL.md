---
name: report_generation
description: >
  Generate a professional PDF report from a structured text file containing
  data analysis results. The workflow is:
  (1) parse the .txt file and identify all sections, tables, lists, and image descriptions,
  (2) for each section decide what visualization fits (table, bar chart, doughnut, line),
  (3) build a SINGLE self-contained HTML file with:
      - styled tables (Blue Professional design tokens),
      - inline Chart.js charts generated from the parsed data,
      - narrative text,
  (4) export the HTML to A4 portrait PDF via Playwright.

  NO external PNG files are used. All visuals are generated dynamically from
  the text content at runtime.
---

# Phase 1 — Parse and analyze the source text

1. Read the source `.txt` file (e.g. `Report_YYYY-MM-DD.txt`).
2. Split by `##` section headers.
3. For each section, identify:
   - Markdown tables → render as styled HTML tables
   - Image descriptions (`![alt](file.png)` or `![description]`) → generate Chart.js charts
   - Numbered lists / bullet points with numeric values → extract for charts
   - Paragraphs with key figures → extract for single-value / comparison charts
4. **Do NOT use any external PNG files.** Ignore the file paths in `![...](...)`.

# Phase 1.5 — Choose chart types dynamically

For each image description, choose chart type based on the description keywords:

| Description keywords | Chart type |
|---|---|
| "comparison", "vs", "target", "actual", "amount" | **bar** (vertical grouped) |
| "top", "ranking", "by customer", "by product" | **bar** (horizontal if many labels) |
| "industry", "breakdown", "distribution", "proportion", "percentage", "share" | **doughnut** or **pie** |
| "trend", "over time", "monthly", "growth", "by month" | **line** |

Extract labels and values from the nearest table, list, or paragraph in the same section.

# Phase 1.6 — Axis scaling and unit annotation

Before rendering charts, inspect the magnitude of numeric values:

| Condition | Action | Annotation |
|---|---|---|
| `max(value) >= 500,000,000` | Divide by 1,000,000 | Append 'M (millions)' |
| `max(value) >= 500,000` | Divide by 1,000 | Append 'k (thousands)' |
| Otherwise | Keep raw | Append original currency unit |

Implementation in Chart.js:
- Rescale the **data array** before passing it to Chart.js (e.g. `value / 1000`).
- Add a `ticks.callback` to the value axis that appends the unit symbol (e.g. `return value + 'k';`).
- Display the unit annotation beneath the chart in a small muted caption (e.g. `<div class="chart-unit">Unit: k (thousands)</div>`).



# Phase 2 — Build the self-contained HTML

## 2.1 Design system (Blue Professional)

Mandatory tokens:
- `colors.bg`          = `#fdfae7`
- `colors.primary`     = `#1e2bfa`
- `colors.text`        = `#111111`
- `colors.text-muted`  = `#6b6b6b`
- `colors.text-light`  = `#9a9a9a`
- `colors.card-bg`     = `rgba(30,43,250,0.04)`
- `colors.border`      = `rgba(30,43,250,0.2)`
- `radii.card-lg`      = `14px`
- `typography.body`    = Inter 400, 1.6 line-height
- `typography.h2`      = Space Grotesk 600

## 2.2 Table styling

Each Markdown table becomes:

```html
<div class="table-wrap">
  <table>
    <thead><tr><th>...</th></tr></thead>
    <tbody><tr><td>...</td></tr></tbody>
  </table>
</div>
```

CSS:
- `.table-wrap`: border-radius 14px, border 1.5px solid `rgba(30,43,250,0.2)`, overflow hidden
- `thead`: background `#1e2bfa`, color `#fdfae7`, font Space Grotesk 600
- `tbody tr:nth-child(even)`: background `rgba(30,43,250,0.04)`
- `tbody tr:nth-child(odd)`: background `#fdfae7`

## 2.3 Chart.js inline charts

Load Chart.js from CDN:
```html
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
```

### CSS container padding (prevent axis clipping)

Apply generous left padding to `.chart-container` so axis labels are never clipped by the canvas edge or the page margin:

```css
.chart-container {
  max-width: 520px;
  margin: 14pt auto;
  padding-left: 35pt;   /* reserve space for long tick labels like "1,234.5k" */
  page-break-inside: avoid;
}
```

### Chart.js layout padding (mandatory for all charts)

Every Chart.js configuration must include a `layout.padding` object. This reserves inner canvas padding so tick labels, legends, or rotated text do not overflow:

```javascript
options: {
  responsive: true,
  layout: {
    padding: {
      left: 30,   // always reserve for longest Y-axis / X-axis tick
      right: 10,
      top: 10,
      bottom: 10
    }
  },
  // ... other options
}
```

### Tick-length guard

When `ticks.callback` appends unit symbols (e.g. `'k'`, `'M'`), estimate the longest string length:
- If the longest tick text could exceed **5 characters**, use `layout.padding.left: 30` (vertical bar) or `layout.padding.right: 20` (horizontal bar).
- For doughnut/pie charts where legends are on the right, use `layout.padding.right: 30`.

### Axis-specific rules

| Chart type | Axis that carries values | Required padding key |
|---|---|---|
| Vertical bar (`type: 'bar'`) | Y-axis | `layout.padding.left: 30` |
| Horizontal bar (`indexAxis: 'y'`) | X-axis | `layout.padding.left: 10`, `layout.padding.right: 20` |
| Line | Y-axis | `layout.padding.left: 30` |
| Doughnut / Pie | None (legend on right) | `layout.padding.right: 30` |

Use Blue Professional tokens for all chart elements:
- chart background: `#fdfae7`
- primary palette: `#1e2bfa` + stepped opacities
- fonts: Inter / Space Grotesk

Charts are part of the HTML — **no screenshot step required**.

## 2.4 Page & print CSS

```css
@page {
  size: A4 portrait;
  margin: 20mm;
}
h2, .section-header {
  page-break-before: always;
}
table, img, blockquote, .card, .chart-container {
  page-break-inside: avoid;
}
```

## 2.5 Execution flow

1. Generate `temp_report.html`:
   - Convert all narrative text to HTML.
   - Insert styled tables inline.
   - Insert Chart.js `<canvas>` elements inline (NOT as external PNGs).
   - Apply Blue Professional CSS tokens inline or via `<style>`.
2. Load with Playwright:
   - `page.goto(f"file://{html_path}", wait_until="networkidle")`
   - Wait for all Chart.js charts to render (use `page.wait_for_timeout(2000)` after load).
3. Export PDF:
   - `page.pdf(path=output_pdf, format="A4", print_background=True, margin={"top":"20mm","right":"20mm","bottom":"20mm","left":"20mm"})`
4. Cleanup:
   - Delete `temp_report.html` after PDF is successfully written.

# Output

- PDF filename: same as the source `.txt`, extension changed to `.pdf`
  - Example: `Report_2026-08-12.txt` → `Report_2026-08-12.pdf`
- Language: match the source text language.
- All visuals are generated from the `.txt` content — no external PNG dependencies.
