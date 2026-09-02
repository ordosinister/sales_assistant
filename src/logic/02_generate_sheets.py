#!/usr/bin/env python3
"""Read SGE Excel and generate analysis Excel with 5 sheets."""

import argparse
from datetime import datetime

import pandas as pd

_MONTH_ABBREV = {1: "Jan", 2: "Feb", 3: "Mar", 4: "Apr", 5: "May", 6: "Jun", 7: "Jul", 8: "Aug", 9: "Sep", 10: "Oct", 11: "Nov", 12: "Dec"}


def get_analysis_period(now: datetime):
    """Determine (year, completed_month, quarter).

    Quarter definitions:
        Q1 = Jan-Mar,  Q2 = Jan-Jun,
        Q3 = Jan-Sep,  Q4 = Jan-Dec

    Settlement rule: use the last *fully completed* quarter.
    - Jan-Mar  -> previous year Q4 (Dec)
    - Apr-Jun  -> Q1 (Mar)
    - Jul-Sep  -> Q2 (Jun)
    - Oct-Dec  -> Q3 (Sep)
    """
    month = now.month
    year = now.year

    if month <= 3:
        return year - 1, 12, 4
    elif month <= 6:
        return year, 3, 1
    elif month <= 9:
        return year, 6, 2
    else:
        return year, 9, 3


def generate_sheets(input_path: str, output_path: str, target_usd: float):
    df = pd.read_excel(input_path)
    df.columns = [c.strip() for c in df.columns]

    df["Order qty"] = pd.to_numeric(df["Order qty"], errors="coerce").fillna(0)
    df["Total shipment amount in US$"] = pd.to_numeric(df["Total shipment amount in US$"], errors="coerce").fillna(0)
    df["Shipped month"] = pd.to_numeric(df["Shipped month"], errors="coerce").fillna(0).astype(int)
    df["Shipped year"] = pd.to_numeric(df["Shipped year"], errors="coerce").fillna(0).astype(int)

    now = datetime.now()
    analysis_year, end_month, quarter = get_analysis_period(now)
    prev_year = analysis_year - 1
    period_label = f"Jan-{_MONTH_ABBREV[end_month]}"

    # ---- Sheet 1: Revenue Achievement Rate ----
    df_period = df[df["Shipped month"] <= end_month]
    current_usd = df_period[df_period["Shipped year"] == analysis_year]["Total shipment amount in US$"].sum()
    achievement_rate = (current_usd / target_usd * 100) if target_usd else 0
    sheet1 = pd.DataFrame(
        {
            "Metric": [
                "Target Revenue (USD)",
                f"Actual Revenue {period_label} (USD)",
                "Achievement Rate (%)",
            ],
            "Value": [target_usd, current_usd, achievement_rate],
        }
    )

    # ---- Sheet 2: Year-over-Year Comparison ----
    current_total = df_period[df_period["Shipped year"] == analysis_year]["Total shipment amount in US$"].sum()
    prev_total = df_period[df_period["Shipped year"] == prev_year]["Total shipment amount in US$"].sum()
    sheet2 = pd.DataFrame(
        {
            "Year": [prev_year, analysis_year],
            f"Total Shipment Amount {period_label} (USD)": [prev_total, current_total],
        }
    )

    # ---- Sheet 3: Top 5 End Customers (analysis_year Jan-end_month) ----
    df_year_period = df_period[df_period["Shipped year"] == analysis_year]
    top5_customers = (
        df_year_period.groupby("Name of end customer")
        .agg({"Order qty": "sum", "Total shipment amount in US$": "sum"})
        .sort_values("Total shipment amount in US$", ascending=False)
        .head(5)
        .reset_index()
    )
    top5_customers.columns = ["End Customer", "Total Qty", "Total USD"]
    sheet3 = top5_customers

    # ---- Sheet 4: Top 5 Industries and End Customers ----
    industry_summary = (
        df_year_period.groupby("Industry")
        .agg({"Order qty": "sum", "Total shipment amount in US$": "sum"})
        .sort_values("Total shipment amount in US$", ascending=False)
        .head(5)
        .reset_index()
    )
    industry_summary.columns = ["Industry", "Total Qty", "Total USD"]

    rows = []
    for _, row in industry_summary.iterrows():
        rows.append(
            {
                "Industry": row["Industry"],
                "End Customer": "(Industry Total)",
                "Total Qty": row["Total Qty"],
                "Total USD": row["Total USD"],
            }
        )
        top_custs = (
            df_year_period[df_year_period["Industry"] == row["Industry"]]
            .groupby("Name of end customer")
            .agg({"Order qty": "sum", "Total shipment amount in US$": "sum"})
            .sort_values("Total shipment amount in US$", ascending=False)
            .head(5)
            .reset_index()
        )
        for _, c in top_custs.iterrows():
            rows.append(
                {
                    "Industry": "",
                    "End Customer": c["Name of end customer"],
                    "Total Qty": c["Order qty"],
                    "Total USD": c["Total shipment amount in US$"],
                }
            )
    sheet4 = pd.DataFrame(rows)

    # ---- Sheet 5: Product Category Summary ----
    sheet5 = (
        df_year_period.groupby("Product type")
        .agg({"Order qty": "sum", "Total shipment amount in US$": "sum"})
        .sort_values("Total shipment amount in US$", ascending=False)
        .reset_index()
    )
    sheet5.columns = ["Product Type", "Total Qty", "Total USD"]
    sheet5 = sheet5.sort_values("Total USD", ascending=False).reset_index(drop=True)

    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        sheet1.to_excel(writer, sheet_name="Revenue Achievement", index=False)
        sheet2.to_excel(writer, sheet_name="YoY Comparison", index=False)
        sheet3.to_excel(writer, sheet_name="Top 5 Customers", index=False)
        sheet4.to_excel(writer, sheet_name="Top 5 Industries", index=False)
        sheet5.to_excel(writer, sheet_name="Product Summary", index=False)

    print(output_path)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("input_path")
    parser.add_argument("output_path")
    parser.add_argument("target_usd", type=float)
    args = parser.parse_args()
    generate_sheets(args.input_path, args.output_path, args.target_usd)
