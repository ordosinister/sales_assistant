#!/usr/bin/env python3
"""Read analysis Excel and generate self-contained HTML report with Chart.js."""
import argparse
import json
from datetime import datetime

import pandas as pd

COLORS = {
    "bg": "#fdfae7",
    "primary": "#1e2bfa",
    "text": "#111111",
    "text_muted": "#6b6b6b",
    "text_light": "#9a9a9a",
    "card_bg": "rgba(30,43,250,0.04)",
    "border": "rgba(30,43,250,0.2)",
}

# High-contrast diverse palette for doughnut chart
DOUGHNUT_PALETTE = ["#FF6B35", "#F7C548", "#6A994E", "#1D3557", "#E63946", "#457B9D"]


def fmt_num(v, decimals=0):
    if v is None:
        return ""
    try:
        f = float(v)
        if decimals == 0 or f == int(f):
            return f"{int(f):,}"
        return f"{f:,.{decimals}f}"
    except (ValueError, TypeError):
        return str(v)


def rescale_for_axis(values):
    max_val = max(float(v) for v in values if v is not None and v != "")
    if max_val >= 500_000_000:
        return [v / 1_000_000 for v in values], "M (millions)", 1_000_000
    elif max_val >= 500_000:
        return [v / 1_000 for v in values], "k (thousands)", 1_000
    else:
        return values, "USD", 1


def tick_suffix(unit: str) -> str:
    if unit == "USD":
        return ""
    if " " in unit:
        return unit.split()[0]
    return unit


def build_html(xlsx_path: str) -> str:
    sheets = pd.read_excel(xlsx_path, sheet_name=None)
    now = datetime.now()
    report_date = now.strftime("%Y-%m-%d")

    s1 = sheets["Revenue Achievement"]
    target = s1.iloc[0]["Value"]
    actual = s1.iloc[1]["Value"]
    rate = s1.iloc[2]["Value"]
    period_label = ""
    m = str(s1.iloc[1]["Metric"])
    if "Jan-" in m:
        period_label = m.split("Jan-")[-1].split(" ")[0]

    s2 = sheets["YoY Comparison"]
    year_prev = int(s2.iloc[0]["Year"])
    year_curr = int(s2.iloc[1]["Year"])
    prev_total = s2.iloc[0].iloc[1]
    curr_total = s2.iloc[1].iloc[1]

    s3 = sheets["Top 5 Customers"]
    s4 = sheets["Top 5 Industries"]
    s5 = sheets["Product Summary"]

    chart_a_data = [actual, target]
    chart_a_labels = [f"Actual (Jan-{period_label})", "Target"]
    a_rescaled, a_unit, _ = rescale_for_axis(chart_a_data)
    a_data_js = json.dumps(a_rescaled)
    a_labels_js = json.dumps(chart_a_labels)
    a_tick = tick_suffix(a_unit)

    chart_b_data = [prev_total, curr_total]
    chart_b_labels = [str(year_prev), str(year_curr)]
    b_rescaled, b_unit, _ = rescale_for_axis(chart_b_data)
    b_data_js = json.dumps(b_rescaled)
    b_labels_js = json.dumps(chart_b_labels)
    b_tick = tick_suffix(b_unit)

    cust_labels = s3["End Customer"].tolist()
    cust_values = s3["Total USD"].tolist()
    c_rescaled, c_unit, _ = rescale_for_axis(cust_values)
    c_data_js = json.dumps(c_rescaled)
    c_labels_js = json.dumps(cust_labels)
    c_tick = tick_suffix(c_unit)

    ind_labels = s4[s4["End Customer"] == "(Industry Total)"]["Industry"].tolist()
    ind_values = s4[s4["End Customer"] == "(Industry Total)"]["Total USD"].tolist()
    d_data_js = json.dumps(ind_values)
    d_labels_js = json.dumps(ind_labels)

    prod_top = s5.head(10)
    prod_labels = prod_top["Product Type"].tolist()
    prod_values = prod_top["Total USD"].tolist()
    e_rescaled, e_unit, _ = rescale_for_axis(prod_values)
    e_data_js = json.dumps(e_rescaled)
    e_labels_js = json.dumps(prod_labels)
    e_tick = tick_suffix(e_unit)

    def table_from_df(df):
        html = '<div class="table-wrap"><table><thead><tr>'
        for col in df.columns:
            html += f"<th>{col}</th>"
        html += "</tr></thead><tbody>"
        for _, row in df.iterrows():
            html += "<tr>"
            for val in row:
                v = val if val is not None else ""
                try:
                    float(v)
                    html += f'<td class="num">{fmt_num(v, 0 if float(v) == int(float(v)) else 2)}</td>'
                except (ValueError, TypeError):
                    html += f"<td>{v}</td>"
            html += "</tr>"
        html += "</tbody></table></div>"
        return html

    t1 = table_from_df(s1)
    t2 = table_from_df(s2)
    t3 = table_from_df(s3)
    t4 = table_from_df(s4)
    t5 = table_from_df(s5)

    ind_palette = json.dumps(DOUGHNUT_PALETTE[: len(ind_labels)])

    html = f"""
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Sales Analysis Report</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
<style>
@page {{ size: A4 portrait; margin: 20mm; }}
body {{ margin: 0; padding: 0; font-family: Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: {COLORS["bg"]}; color: {COLORS["text"]}; font-size: 14px; line-height: 1.6; }}
.container {{ max-width: 900px; margin: 0 auto; padding: 24px; }}
.header {{ background: {COLORS["primary"]}; color: #fff; padding: 18px 24px; border-radius: 14px; margin-bottom: 20px; }}
.header h1 {{ font-family: "Space Grotesk", sans-serif; font-size: 28px; font-weight: 600; margin: 0; }}
.header .sub {{ font-size: 12px; opacity: 0.85; margin-top: 6px; }}
.kpi-grid {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 14px; margin-bottom: 20px; }}
.kpi {{ background: {COLORS["card_bg"]}; border: 1.5px solid {COLORS["border"]}; border-radius: 14px; padding: 16px; text-align: center; }}
.kpi-value {{ font-size: 22px; font-weight: 700; color: {COLORS["primary"]}; }}
.kpi-label {{ font-size: 11px; color: {COLORS["text_muted"]}; margin-top: 4px; text-transform: uppercase; letter-spacing: 0.5px; }}
.section-header {{ background: {COLORS["primary"]}; color: #fff; padding: 8px 16px; font-size: 16px; font-weight: 600; border-radius: 14px; margin-top: 24px; }}
.section-body {{ background: {COLORS["card_bg"]}; border: 1.5px solid {COLORS["border"]}; border-top: none; border-radius: 0 0 14px 14px; padding: 16px; }}
.table-wrap {{ border-radius: 14px; border: 1.5px solid {COLORS["border"]}; overflow: hidden; margin-bottom: 12px; }}
table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
thead {{ background: {COLORS["primary"]}; color: #fff; font-family: "Space Grotesk", sans-serif; font-weight: 600; }}
th {{ padding: 8px 12px; text-align: left; }}
td {{ padding: 6px 12px; border-bottom: 1px solid {COLORS["border"]}; }}
tbody tr:nth-child(even) {{ background: {COLORS["card_bg"]}; }}
tbody tr:nth-child(odd) {{ background: {COLORS["bg"]}; }}
.num {{ text-align: right; font-variant-numeric: tabular-nums; }}
.chart-container {{ max-width: 520px; margin: 14px auto; padding-left: 35px; page-break-inside: avoid; }}
.chart-unit {{ font-size: 11px; color: {COLORS["text_muted"]}; text-align: center; margin-top: 4px; }}
.page-break {{ page-break-before: always; }}
table, .chart-container, .card {{ page-break-inside: avoid; }}
@media (max-width: 560px) {{ .kpi-grid {{ grid-template-columns: 1fr 1fr; }} }}
</style>
</head>
<body>
<div class="container">
<div class="header">
<h1>Sales Analysis Report</h1>
<div class="sub">Report Date: {report_date} &nbsp;|&nbsp; Period: Jan-{period_label} {year_curr} &nbsp;|&nbsp; Data: SGE Sales</div>
</div>

<div class="kpi-grid">
<div class="kpi"><div class="kpi-value">{fmt_num(actual, 0)}</div><div class="kpi-label">Actual Revenue (USD)</div></div>
<div class="kpi"><div class="kpi-value">{fmt_num(target, 0)}</div><div class="kpi-label">Target Revenue (USD)</div></div>
<div class="kpi"><div class="kpi-value">{rate:.2f}%</div><div class="kpi-label">Achievement Rate</div></div>
</div>

<div class="section-header page-break">1. Revenue Achievement Rate</div>
<div class="section-body">
{t1}
<div class="chart-container"><canvas id="chartA"></canvas></div>
<div class="chart-unit">Unit: {a_unit}</div>
</div>

<div class="section-header page-break">2. Year-over-Year Comparison ({year_prev} vs {year_curr})</div>
<div class="section-body">
{t2}
<div class="chart-container"><canvas id="chartB"></canvas></div>
<div class="chart-unit">Unit: {b_unit}</div>
</div>

<div class="section-header page-break">3. Top 5 End Customers ({year_curr})</div>
<div class="section-body">
{t3}
<div class="chart-container"><canvas id="chartC"></canvas></div>
<div class="chart-unit">Unit: {c_unit}</div>
</div>

<div class="section-header page-break">4. Top 5 Industries and End Customers ({year_curr})</div>
<div class="section-body">{t4}</div>

<div class="section-header page-break">4. Top 5 Industries — Chart</div>
<div class="section-body">
<div class="chart-container"><canvas id="chartD"></canvas></div>
</div>

<div class="section-header page-break">5. Product Category Summary ({year_curr})</div>
<div class="section-body">{t5}</div>

<div class="section-header page-break">5. Product Category Summary — Chart</div>
<div class="section-body">
<div class="chart-container"><canvas id="chartE"></canvas></div>
<div class="chart-unit">Unit: {e_unit}</div>
</div>

<script>
Chart.defaults.font.family = 'Inter, sans-serif';
Chart.defaults.color = '{COLORS["text"]}';

new Chart(document.getElementById('chartA'), {{
  type: 'bar',
  data: {{ labels: {a_labels_js}, datasets: [{{ label: 'USD', data: {a_data_js}, backgroundColor: ['{COLORS["primary"]}', 'rgba(30,43,250,0.3)'], borderRadius: 6 }}] }},
  options: {{ responsive: true, layout: {{ padding: {{ left: 30, right: 10, top: 10, bottom: 10 }} }}, plugins: {{ legend: {{ display: false }} }}, scales: {{ y: {{ beginAtZero: true, ticks: {{ callback: v => v + '{a_tick}' }} }} }} }}
}});

new Chart(document.getElementById('chartB'), {{
  type: 'bar',
  data: {{ labels: {b_labels_js}, datasets: [{{ label: 'USD', data: {b_data_js}, backgroundColor: ['rgba(30,43,250,0.3)', '{COLORS["primary"]}'], borderRadius: 6 }}] }},
  options: {{ responsive: true, layout: {{ padding: {{ left: 30, right: 10, top: 10, bottom: 10 }} }}, plugins: {{ legend: {{ display: false }} }}, scales: {{ y: {{ beginAtZero: true, ticks: {{ callback: v => v + '{b_tick}' }} }} }} }}
}});

new Chart(document.getElementById('chartC'), {{
  type: 'bar',
  data: {{ labels: {c_labels_js}, datasets: [{{ label: 'USD', data: {c_data_js}, backgroundColor: '{COLORS["primary"]}', borderRadius: 6 }}] }},
  options: {{ indexAxis: 'y', responsive: true, layout: {{ padding: {{ left: 10, right: 20, top: 10, bottom: 10 }} }}, plugins: {{ legend: {{ display: false }} }}, scales: {{ x: {{ beginAtZero: true, ticks: {{ callback: v => v + '{c_tick}' }} }} }} }}
}});

new Chart(document.getElementById('chartD'), {{
  type: 'doughnut',
  data: {{ labels: {d_labels_js}, datasets: [{{ data: {d_data_js}, backgroundColor: {ind_palette}, borderWidth: 0 }}] }},
  options: {{ responsive: true, layout: {{ padding: {{ left: 10, right: 30, top: 10, bottom: 10 }} }}, plugins: {{ legend: {{ position: 'right' }} }} }}
}});

new Chart(document.getElementById('chartE'), {{
  type: 'bar',
  data: {{ labels: {e_labels_js}, datasets: [{{ label: 'USD', data: {e_data_js}, backgroundColor: '{COLORS["primary"]}', borderRadius: 6 }}] }},
  options: {{ indexAxis: 'y', responsive: true, layout: {{ padding: {{ left: 10, right: 20, top: 10, bottom: 10 }} }}, plugins: {{ legend: {{ display: false }} }}, scales: {{ x: {{ beginAtZero: true, ticks: {{ callback: v => v + '{e_tick}' }} }} }} }}
}});
</script>
</div>
</body>
</html>
"""
    return html


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("xlsx_path")
    parser.add_argument("html_path")
    args = parser.parse_args()
    html = build_html(args.xlsx_path)
    with open(args.html_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(args.html_path)


if __name__ == "__main__":
    main()