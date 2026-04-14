#!/usr/bin/env python3

import argparse
from pathlib import Path

try:
    from affiliation_pipeline import AUTHOR_FIELDS, COUNTRY_FIELDS, apply_inferred_countries, build_country_rows, load_csv, write_csv
    from fill_unknown_countries_with_local_llm import REVIEW_FIELDS, count_applied_updates, fill_unknown_countries_with_local_llm
except ModuleNotFoundError:
    from scripts.affiliation_pipeline import AUTHOR_FIELDS, COUNTRY_FIELDS, apply_inferred_countries, build_country_rows, load_csv, write_csv
    from scripts.fill_unknown_countries_with_local_llm import REVIEW_FIELDS, count_applied_updates, fill_unknown_countries_with_local_llm


def main():
    parser = argparse.ArgumentParser(description="Infer countries from normalized institution strings.")
    parser.add_argument("--authors-csv", required=True)
    parser.add_argument("--output-authors-csv", required=True)
    parser.add_argument("--output-countries-csv", required=True)
    parser.add_argument("--use-local-llm", action="store_true", help="Use the shared local Ollama model as a fallback for rows with known institution but UNKNOWN country.")
    parser.add_argument("--llm-config", default=str(Path(__file__).resolve().parent.parent / "config" / "local_llm.json"))
    parser.add_argument("--llm-review-csv", help="Optional CSV file for local-LLM review output.")
    parser.add_argument("--llm-min-confidence", choices=["low", "medium", "high"], default="medium")
    parser.add_argument("--llm-limit", type=int)
    args = parser.parse_args()

    authors = load_csv(Path(args.authors_csv))
    authors = apply_inferred_countries(authors)
    review_rows = []
    if args.use_local_llm:
        authors, review_rows = fill_unknown_countries_with_local_llm(
            authors,
            config_path=Path(args.llm_config),
            min_confidence=args.llm_min_confidence,
            limit=args.llm_limit,
        )

    country_rows = build_country_rows(authors)
    write_csv(Path(args.output_authors_csv), AUTHOR_FIELDS, authors)
    write_csv(Path(args.output_countries_csv), COUNTRY_FIELDS, country_rows)
    if args.use_local_llm and args.llm_review_csv:
        write_csv(Path(args.llm_review_csv), REVIEW_FIELDS, review_rows)
    inferred = sum(1 for row in authors if row["country"] != "UNKNOWN")
    if args.use_local_llm:
        print(
            f"Inferred non-UNKNOWN countries for {inferred} author rows; "
            f"local LLM applied {count_applied_updates(review_rows)} updates"
        )
    else:
        print(f"Inferred non-UNKNOWN countries for {inferred} author rows")


if __name__ == "__main__":
    main()
