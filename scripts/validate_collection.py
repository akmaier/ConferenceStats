#!/usr/bin/env python3

import argparse
import csv
from pathlib import Path


REQUIRED_FILES = ("authors.csv", "papers.csv", "paper_authors.csv")

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


def find_dataset_roots(input_dir: Path):
    for conference_dir in sorted(p for p in input_dir.iterdir() if p.is_dir()):
        for year_dir in sorted(p for p in conference_dir.iterdir() if p.is_dir()):
            if all((year_dir / filename).exists() for filename in REQUIRED_FILES):
                yield year_dir


def ensure_columns(path: Path, actual_columns, required_columns):
    missing = required_columns - set(actual_columns)
    if missing:
        missing_list = ", ".join(sorted(missing))
        raise ValueError(f"{path} is missing required columns: {missing_list}")


def ensure_unique(rows, key, path: Path):
    seen = set()
    for row in rows:
        value = row[key]
        if value in seen:
            raise ValueError(f"{path} contains duplicate {key}: {value}")
        seen.add(value)


def validate_dataset(dataset_dir: Path):
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

    ensure_unique(author_rows, "author_id", dataset_dir / "authors.csv")
    ensure_unique(paper_rows, "paper_id", dataset_dir / "papers.csv")

    author_ids = {row["author_id"] for row in author_rows}
    paper_ids = {row["paper_id"] for row in paper_rows}

    for row in link_rows:
        if row["author_id"] not in author_ids:
            raise ValueError(
                f"{dataset_dir / 'paper_authors.csv'} references unknown author_id {row['author_id']}"
            )
        if row["paper_id"] not in paper_ids:
            raise ValueError(
                f"{dataset_dir / 'paper_authors.csv'} references unknown paper_id {row['paper_id']}"
            )


def main():
    parser = argparse.ArgumentParser(
        description="Validate normalized conference collection datasets."
    )
    parser.add_argument("--input-dir", required=True, help="Directory containing normalized data.")
    args = parser.parse_args()

    input_dir = Path(args.input_dir)
    dataset_dirs = list(find_dataset_roots(input_dir))
    if not dataset_dirs:
        raise SystemExit(f"No normalized datasets found under {input_dir}")

    for dataset_dir in dataset_dirs:
        validate_dataset(dataset_dir)

    print(f"Validated {len(dataset_dirs)} dataset(s) under {input_dir}")


if __name__ == "__main__":
    main()
