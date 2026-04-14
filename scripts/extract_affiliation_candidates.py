#!/usr/bin/env python3

import argparse
from pathlib import Path

from affiliation_pipeline import CANDIDATE_FIELDS, extract_candidate_rows, load_csv, write_csv


def main():
    parser = argparse.ArgumentParser(description="Extract raw author-affiliation candidates from first-page text.")
    parser.add_argument("--authors-csv", required=True)
    parser.add_argument("--paper-authors-csv", required=True)
    parser.add_argument("--papers-index", required=True)
    parser.add_argument("--first-pages-dir", required=True)
    parser.add_argument("--output-candidates-csv", required=True)
    args = parser.parse_args()

    authors = load_csv(Path(args.authors_csv))
    paper_authors = load_csv(Path(args.paper_authors_csv))
    papers_index_rows = load_csv(Path(args.papers_index))
    candidate_rows = extract_candidate_rows(
        authors,
        paper_authors,
        papers_index_rows,
        Path(args.first_pages_dir),
    )
    write_csv(Path(args.output_candidates_csv), CANDIDATE_FIELDS, candidate_rows)
    print(f"Wrote {len(candidate_rows)} candidate rows to {args.output_candidates_csv}")


if __name__ == "__main__":
    main()
