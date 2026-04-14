#!/usr/bin/env python3

import argparse
from pathlib import Path

from affiliation_pipeline import (
    AUTHOR_FIELDS,
    INSTITUTION_FIELDS,
    apply_selected_institutions,
    build_institution_rows,
    load_csv,
    write_csv,
)


def main():
    parser = argparse.ArgumentParser(description="Normalize linked author affiliations into authors.csv.")
    parser.add_argument("--authors-csv", required=True)
    parser.add_argument("--links-csv", required=True)
    parser.add_argument("--output-authors-csv", required=True)
    parser.add_argument("--output-institutions-csv", required=True)
    args = parser.parse_args()

    authors = load_csv(Path(args.authors_csv))
    link_rows = load_csv(Path(args.links_csv))
    authors = apply_selected_institutions(authors, link_rows)
    institution_rows = build_institution_rows(link_rows)
    write_csv(Path(args.output_authors_csv), AUTHOR_FIELDS, authors)
    write_csv(Path(args.output_institutions_csv), INSTITUTION_FIELDS, institution_rows)
    enriched = sum(1 for row in authors if row["institution"] != "UNKNOWN")
    print(f"Normalized institutions for {enriched} author rows")


if __name__ == "__main__":
    main()
