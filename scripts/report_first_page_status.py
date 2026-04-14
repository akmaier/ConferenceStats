#!/usr/bin/env python3

import argparse
import csv
from pathlib import Path


def count_csv_rows(path: Path) -> int | None:
    if not path.exists():
        return None
    with path.open(newline="", encoding="utf-8") as handle:
        return len(list(csv.DictReader(handle)))


def main():
    parser = argparse.ArgumentParser(description="Summarize first-page extraction status across CVPR years.")
    parser.add_argument("--conference-slug", default="cvpr")
    parser.add_argument("--start-year", type=int, required=True)
    parser.add_argument("--end-year", type=int, required=True)
    args = parser.parse_args()

    print("year,papers_index_rows,manifest_rows,manifest_ok,manifest_error,txt_files")
    for year in range(args.start_year, args.end_year + 1):
        raw_dir = Path(f"data/raw/{args.conference_slug}/{year}")
        papers_index = raw_dir / "papers_index.csv"
        manifest = raw_dir / "first_page_manifest.csv"
        first_pages = raw_dir / "first_pages"

        papers_index_rows = count_csv_rows(papers_index)
        manifest_rows = None
        manifest_ok = None
        manifest_error = None
        if manifest.exists():
            with manifest.open(newline="", encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))
            manifest_rows = len(rows)
            manifest_ok = sum(row.get("status") == "ok" for row in rows)
            manifest_error = sum(row.get("status") == "error" for row in rows)

        txt_files = len(list(first_pages.glob("*.txt"))) if first_pages.exists() else 0
        print(
            f"{year},{papers_index_rows if papers_index_rows is not None else ''},"
            f"{manifest_rows if manifest_rows is not None else ''},"
            f"{manifest_ok if manifest_ok is not None else ''},"
            f"{manifest_error if manifest_error is not None else ''},"
            f"{txt_files}"
        )


if __name__ == "__main__":
    main()
