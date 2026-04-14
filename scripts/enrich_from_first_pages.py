#!/usr/bin/env python3

import argparse
from pathlib import Path

try:
    from affiliation_pipeline import (
        AUTHOR_FIELDS,
        CANDIDATE_FIELDS,
        COUNTRY_FIELDS,
        INSTITUTION_FIELDS,
        LINK_FIELDS,
        apply_inferred_countries,
        apply_selected_institutions,
        build_country_rows,
        build_institution_rows,
        extract_candidate_rows,
        load_csv,
        select_affiliation_links,
        write_csv,
    )
    from fill_unknown_countries_with_local_llm import REVIEW_FIELDS, count_applied_updates, fill_unknown_countries_with_local_llm
except ModuleNotFoundError:
    from scripts.affiliation_pipeline import (
        AUTHOR_FIELDS,
        CANDIDATE_FIELDS,
        COUNTRY_FIELDS,
        INSTITUTION_FIELDS,
        LINK_FIELDS,
        apply_inferred_countries,
        apply_selected_institutions,
        build_country_rows,
        build_institution_rows,
        extract_candidate_rows,
        load_csv,
        select_affiliation_links,
        write_csv,
    )
    from scripts.fill_unknown_countries_with_local_llm import REVIEW_FIELDS, count_applied_updates, fill_unknown_countries_with_local_llm


def main():
    parser = argparse.ArgumentParser(description="Run the multi-pass first-page enrichment pipeline.")
    parser.add_argument("--authors-csv", required=True)
    parser.add_argument("--papers-csv")
    parser.add_argument("--paper-authors-csv", required=True)
    parser.add_argument("--papers-index", required=True)
    parser.add_argument("--first-pages-dir", required=True)
    parser.add_argument("--output-authors-csv", required=True)
    parser.add_argument("--output-affiliations-csv")
    parser.add_argument("--intermediate-dir")
    parser.add_argument("--output-candidates-csv")
    parser.add_argument("--output-links-csv")
    parser.add_argument("--output-institutions-csv")
    parser.add_argument("--output-countries-csv")
    parser.add_argument("--min-score", type=int, default=2)
    parser.add_argument("--use-local-llm", action="store_true", help="Use the shared local Ollama model as a fallback for rows with known institution but UNKNOWN country.")
    parser.add_argument("--llm-config", default=str(Path(__file__).resolve().parent.parent / "config" / "local_llm.json"))
    parser.add_argument("--output-llm-review-csv")
    parser.add_argument("--llm-min-confidence", choices=["low", "medium", "high"], default="medium")
    parser.add_argument("--llm-limit", type=int)
    args = parser.parse_args()

    authors = load_csv(Path(args.authors_csv))
    paper_authors = load_csv(Path(args.paper_authors_csv))
    papers_index_rows = load_csv(Path(args.papers_index))

    intermediate_dir = Path(args.intermediate_dir) if args.intermediate_dir else None
    output_candidates = (
        Path(args.output_candidates_csv)
        if args.output_candidates_csv
        else (intermediate_dir / "affiliation_candidates.csv" if intermediate_dir else None)
    )
    output_links = (
        Path(args.output_links_csv)
        if args.output_links_csv
        else (
            Path(args.output_affiliations_csv)
            if args.output_affiliations_csv
            else (intermediate_dir / "author_affiliations.csv" if intermediate_dir else None)
        )
    )
    output_institutions = (
        Path(args.output_institutions_csv)
        if args.output_institutions_csv
        else (intermediate_dir / "author_institutions.csv" if intermediate_dir else None)
    )
    output_countries = (
        Path(args.output_countries_csv)
        if args.output_countries_csv
        else (intermediate_dir / "author_countries.csv" if intermediate_dir else None)
    )
    output_llm_review = (
        Path(args.output_llm_review_csv)
        if args.output_llm_review_csv
        else (intermediate_dir / "author_country_llm_review.csv" if intermediate_dir and args.use_local_llm else None)
    )

    candidate_rows = extract_candidate_rows(
        authors,
        paper_authors,
        papers_index_rows,
        Path(args.first_pages_dir),
    )
    link_rows = select_affiliation_links(candidate_rows, min_score=args.min_score)
    authors = apply_selected_institutions(authors, link_rows)
    institution_rows = build_institution_rows(link_rows)
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
    if output_candidates:
        write_csv(output_candidates, CANDIDATE_FIELDS, candidate_rows)
    if output_links:
        write_csv(output_links, LINK_FIELDS, link_rows)
    if output_institutions:
        write_csv(output_institutions, INSTITUTION_FIELDS, institution_rows)
    if output_countries:
        write_csv(output_countries, COUNTRY_FIELDS, country_rows)
    if output_llm_review:
        write_csv(output_llm_review, REVIEW_FIELDS, review_rows)

    enriched = sum(row["institution"] != "UNKNOWN" for row in authors)
    if args.use_local_llm:
        print(
            f"Enriched {enriched} author rows with non-UNKNOWN institution values; "
            f"local LLM applied {count_applied_updates(review_rows)} country updates"
        )
    else:
        print(f"Enriched {enriched} author rows with non-UNKNOWN institution values")


if __name__ == "__main__":
    main()
