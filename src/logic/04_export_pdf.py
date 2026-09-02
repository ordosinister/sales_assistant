#!/usr/bin/env python3
"""Export HTML report to PDF via Playwright."""

import argparse
import os

from playwright.sync_api import sync_playwright


def export_pdf(html_path: str, pdf_path: str):
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1200, "height": 800})
        page.goto(f"file:///{os.path.abspath(html_path).replace(chr(92), '/')}", wait_until="networkidle")
        page.wait_for_timeout(2000)
        page.pdf(
            path=pdf_path,
            format="A4",
            print_background=True,
            margin={"top": "20mm", "right": "20mm", "bottom": "20mm", "left": "20mm"},
        )
        browser.close()
    print(pdf_path)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("html_path")
    parser.add_argument("pdf_path")
    args = parser.parse_args()
    export_pdf(args.html_path, args.pdf_path)


if __name__ == "__main__":
    main()
