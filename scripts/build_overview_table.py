#!/usr/bin/env python3

import argparse
import csv
from collections import defaultdict
from pathlib import Path


def load_stats(path: Path):
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def build_pivot(rows, metric_field):
    years = sorted({row["year"] for row in rows}, key=int)
    by_conference = defaultdict(dict)
    for row in rows:
        by_conference[row["conference"]][row["year"]] = row[metric_field]
    conferences = sorted(by_conference, key=str.casefold)
    return conferences, years, by_conference


def write_csv(path: Path, conferences, years, by_conference):
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = ["conference", *years]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for conference in conferences:
            row = {"conference": conference}
            for year in years:
                row[year] = by_conference[conference].get(year, "")
            writer.writerow(row)


def write_markdown(path: Path, title: str, conferences, years, by_conference):
    path.parent.mkdir(parents=True, exist_ok=True)
    headers = ["Conference", *years]
    align = ["---", *["---:" for _ in years]]
    lines = [
        f"# {title}",
        "",
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(align) + " |",
    ]
    for conference in conferences:
        cells = [conference]
        for year in years:
            cells.append(by_conference[conference].get(year, ""))
        lines.append("| " + " | ".join(cells) + " |")
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(
        description="Build a conference-by-year overview table from country stats."
    )
    parser.add_argument("--input-csv", required=True, help="Input country_stats.csv file.")
    parser.add_argument("--country", required=True, help="Country name for titles.")
    parser.add_argument(
        "--output-csv-all",
        required=True,
        help="Output CSV for share over all papers.",
    )
    parser.add_argument(
        "--output-md-all",
        required=True,
        help="Output Markdown for share over all papers.",
    )
    parser.add_argument(
        "--output-csv-known",
        required=True,
        help="Output CSV for share over papers with any known country.",
    )
    parser.add_argument(
        "--output-md-known",
        required=True,
        help="Output Markdown for share over papers with any known country.",
    )
    args = parser.parse_args()

    rows = load_stats(Path(args.input_csv))
    if not rows:
        raise SystemExit(f"No rows found in {args.input_csv}")

    conferences, years, by_conference_all = build_pivot(rows, "share_percent_all_papers")
    write_csv(Path(args.output_csv_all), conferences, years, by_conference_all)
    write_markdown(
        Path(args.output_md_all),
        f"Overview Table: {args.country} (All Papers)",
        conferences,
        years,
        by_conference_all,
    )

    conferences, years, by_conference_known = build_pivot(
        rows, "share_percent_known_country_papers"
    )
    write_csv(Path(args.output_csv_known), conferences, years, by_conference_known)
    write_markdown(
        Path(args.output_md_known),
        f"Overview Table: {args.country} (Known-Country Papers Only)",
        conferences,
        years,
        by_conference_known,
    )


if __name__ == "__main__":
    main()
