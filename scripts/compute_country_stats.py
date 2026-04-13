#!/usr/bin/env python3

import argparse
import csv
from pathlib import Path


REQUIRED_AUTHOR_COLUMNS = {
    "author_id",
    "author_name",
    "country",
    "institution",
    "conference",
    "year",
    "source_url",
    "source_note",
}

REQUIRED_PAPER_COLUMNS = {
    "paper_id",
    "title",
    "author_ids",
    "conference",
    "year",
    "source_url",
}

REQUIRED_PAPER_AUTHOR_COLUMNS = {
    "paper_id",
    "author_id",
    "author_position",
}


def load_csv(path: Path):
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
        return reader.fieldnames or [], rows


def ensure_columns(path: Path, actual_columns, required_columns):
    missing = required_columns - set(actual_columns)
    if missing:
        missing_list = ", ".join(sorted(missing))
        raise ValueError(f"{path} is missing required columns: {missing_list}")


def country_matches(author_country: str, target_country: str) -> bool:
    return author_country.strip().casefold() == target_country.strip().casefold()


def find_dataset_roots(input_dir: Path):
    for conference_dir in sorted(p for p in input_dir.iterdir() if p.is_dir()):
        for year_dir in sorted(p for p in conference_dir.iterdir() if p.is_dir()):
            authors_csv = year_dir / "authors.csv"
            papers_csv = year_dir / "papers.csv"
            paper_authors_csv = year_dir / "paper_authors.csv"
            if authors_csv.exists() and papers_csv.exists() and paper_authors_csv.exists():
                yield year_dir


def compute_stats_for_dataset(dataset_dir: Path, target_country: str):
    author_columns, author_rows = load_csv(dataset_dir / "authors.csv")
    paper_columns, paper_rows = load_csv(dataset_dir / "papers.csv")
    link_columns, link_rows = load_csv(dataset_dir / "paper_authors.csv")

    ensure_columns(dataset_dir / "authors.csv", author_columns, REQUIRED_AUTHOR_COLUMNS)
    ensure_columns(dataset_dir / "papers.csv", paper_columns, REQUIRED_PAPER_COLUMNS)
    ensure_columns(
        dataset_dir / "paper_authors.csv",
        link_columns,
        REQUIRED_PAPER_AUTHOR_COLUMNS,
    )

    authors_by_id = {row["author_id"]: row for row in author_rows}
    papers_by_id = {row["paper_id"]: row for row in paper_rows}

    conference = paper_rows[0]["conference"] if paper_rows else dataset_dir.parent.name
    year = paper_rows[0]["year"] if paper_rows else dataset_dir.name

    matching_paper_ids = set()
    for link in link_rows:
        author = authors_by_id.get(link["author_id"])
        if author is None:
            raise ValueError(
                f"{dataset_dir / 'paper_authors.csv'} references unknown author_id "
                f"{link['author_id']}"
            )
        if link["paper_id"] not in papers_by_id:
            raise ValueError(
                f"{dataset_dir / 'paper_authors.csv'} references unknown paper_id "
                f"{link['paper_id']}"
            )
        if country_matches(author["country"], target_country):
            matching_paper_ids.add(link["paper_id"])

    total_papers = len(paper_rows)
    papers_with_country = len(matching_paper_ids)
    share_percent = (papers_with_country / total_papers * 100.0) if total_papers else 0.0

    return {
        "conference": conference,
        "year": year,
        "country": target_country,
        "total_papers": str(total_papers),
        "papers_with_country": str(papers_with_country),
        "share_percent": f"{share_percent:.2f}",
    }


def write_csv(path: Path, rows):
    fieldnames = [
        "conference",
        "year",
        "country",
        "total_papers",
        "papers_with_country",
        "share_percent",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_markdown(path: Path, rows, country: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        f"# Country Statistics: {country}",
        "",
        "| Conference | Year | Total Papers | Papers With Country | Share % |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for row in rows:
        lines.append(
            "| {conference} | {year} | {total_papers} | {papers_with_country} | {share_percent} |".format(
                **row
            )
        )
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(
        description="Compute conference/year paper shares for a target country."
    )
    parser.add_argument("--input-dir", required=True, help="Directory containing normalized data.")
    parser.add_argument("--country", required=True, help="Country to match.")
    parser.add_argument("--output-csv", required=True, help="Output CSV file.")
    parser.add_argument("--output-md", required=True, help="Output Markdown file.")
    args = parser.parse_args()

    input_dir = Path(args.input_dir)
    dataset_dirs = list(find_dataset_roots(input_dir))
    if not dataset_dirs:
        raise SystemExit(f"No normalized datasets found under {input_dir}")

    rows = [compute_stats_for_dataset(dataset_dir, args.country) for dataset_dir in dataset_dirs]
    rows.sort(key=lambda row: (row["conference"].casefold(), int(row["year"])))

    write_csv(Path(args.output_csv), rows)
    write_markdown(Path(args.output_md), rows, args.country)


if __name__ == "__main__":
    main()
