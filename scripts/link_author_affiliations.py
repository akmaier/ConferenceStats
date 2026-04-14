#!/usr/bin/env python3

import argparse
from pathlib import Path

from affiliation_pipeline import LINK_FIELDS, load_csv, select_affiliation_links, write_csv


def main():
    parser = argparse.ArgumentParser(description="Choose the best affiliation candidate for each author.")
    parser.add_argument("--candidates-csv", required=True)
    parser.add_argument("--output-links-csv", required=True)
    parser.add_argument("--min-score", type=int, default=2)
    args = parser.parse_args()

    candidate_rows = load_csv(Path(args.candidates_csv))
    link_rows = select_affiliation_links(candidate_rows, min_score=args.min_score)
    write_csv(Path(args.output_links_csv), LINK_FIELDS, link_rows)
    chosen = sum(1 for row in link_rows if row["institution_raw"] != "UNKNOWN")
    print(f"Linked {chosen} authors with non-UNKNOWN institution candidates")


if __name__ == "__main__":
    main()
