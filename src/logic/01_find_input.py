#!/usr/bin/env python3
"""Find the input Excel file starting with 'SGE' in the data directory."""

import glob
import os
import sys

DATA_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "data",
)


def main():
    pattern = os.path.join(DATA_DIR, "SGE*.xlsx")
    files = glob.glob(pattern)
    if not files:
        print(f"No SGE*.xlsx found in {DATA_DIR}", file=sys.stderr)
        sys.exit(1)
    # Pick the first match (assume only one)
    print(files[0])


if __name__ == "__main__":
    main()
