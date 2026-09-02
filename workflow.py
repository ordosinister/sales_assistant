#!/usr/bin/env python3
"""Sales Analysis Workflow.

Orchestrates:
  1. Find input SGE*.xlsx in ./data
  2. Generate analysis Excel with 5 sheets
  3. Generate self-contained HTML report with Chart.js
  4. Export HTML to PDF via Playwright
  5. Clean up intermediate files

Usage:
    python workflow.py <target_usd>
    python workflow.py 1200000
"""
import argparse
import os
import subprocess
import sys
from datetime import datetime

REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(REPO_ROOT, "data")
LOGIC_DIR = os.path.join(REPO_ROOT, "src", "logic")
PYTHON = sys.executable


def run_script(script_name: str, *args) -> str:
    """Run a logic script and return stdout (stripped)."""
    cmd = [PYTHON, os.path.join(LOGIC_DIR, script_name)] + list(args)
    result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
    if result.returncode != 0:
        print(f"Error running {script_name}:", file=sys.stderr)
        print(result.stderr, file=sys.stderr)
        sys.exit(result.returncode)
    return result.stdout.strip()


def main():
    parser = argparse.ArgumentParser(description="Sales Analysis Workflow")
    parser.add_argument(
        "target_usd",
        type=float,
        help="Target annual revenue in USD (e.g. 1200000 for .2M)",
    )
    parser.add_argument(
        "--keep-temp", action="store_true", help="Keep intermediate HTML/XLSX files"
    )
    args = parser.parse_args()

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    analysis_xlsx = os.path.join(DATA_DIR, f"analysis_{timestamp}.xlsx")
    report_html = os.path.join(DATA_DIR, f"report_{timestamp}.html")
    report_pdf = os.path.join(DATA_DIR, f"Sales_Report_{timestamp}.pdf")

    # Step 1: find input
    print("[1/4] Finding input Excel...")
    input_xlsx = run_script("01_find_input.py")
    print(f"      Input: {input_xlsx}")

    # Step 2: generate analysis sheets
    print("[2/4] Generating analysis Excel...")
    run_script("02_generate_sheets.py", input_xlsx, analysis_xlsx, str(args.target_usd))
    print(f"      Output: {analysis_xlsx}")

    # Step 3: generate HTML
    print("[3/4] Generating HTML report...")
    run_script("03_generate_html.py", analysis_xlsx, report_html)
    print(f"      Output: {report_html}")

    # Step 4: export PDF
    print("[4/4] Exporting PDF...")
    run_script("04_export_pdf.py", report_html, report_pdf)
    print(f"      Output: {report_pdf}")

    # Cleanup
    if not args.keep_temp:
        print("Cleaning up intermediate files...")
        for path in (analysis_xlsx, report_html):
            if os.path.exists(path):
                os.remove(path)
                print(f"      Removed: {path}")

    print(f"\nDone. PDF saved to: {report_pdf}")


if __name__ == "__main__":
    main()