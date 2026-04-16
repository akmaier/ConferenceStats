#!/usr/bin/env python3

import argparse
import json
import re
import socket
import time
from collections import defaultdict
from pathlib import Path
from urllib.error import URLError

try:
    from affiliation_pipeline import AUTHOR_FIELDS, COUNTRY_FIELDS, build_country_rows, load_csv, normalize_country_value, write_csv
    from local_llm import load_local_llm_config, ollama_chat_json
except ModuleNotFoundError:
    from scripts.affiliation_pipeline import AUTHOR_FIELDS, COUNTRY_FIELDS, build_country_rows, load_csv, normalize_country_value, write_csv
    from scripts.local_llm import load_local_llm_config, ollama_chat_json


REVIEW_FIELDS = [
    "paper_id",
    "author_id",
    "author_name",
    "institution",
    "existing_country",
    "llm_country",
    "llm_confidence",
    "llm_reason",
    "applied",
    "first_page_text_path",
]

CONFIDENCE_RANK = {"low": 1, "medium": 2, "high": 3}
DEFAULT_SOURCE_NOTE = "Country inferred from full first-page text using local Ollama model"

SYSTEM_PROMPT = """You infer author countries from a paper's first-page text.
Return only JSON with this structure:
{
  "authors": [
    {
      "author_name": "...",
      "country": "country name, ` | `-separated country list, or UNKNOWN",
      "confidence": "high|medium|low",
      "reason": "short explanation",
      "keep_unknown": true_or_false
    }
  ]
}
Rules:
- Use only the provided first-page text and author list as evidence.
- Match author names exactly as given in the author list.
- Use canonical country names such as `United States`, `United Kingdom`, `South Korea`, `China`, `Taiwan`.
- If the page shows multiple affiliations for an author in multiple countries, return a ` | `-separated list.
- If the page does not support a reliable country assignment for an author, return UNKNOWN and keep_unknown true.
- Never infer from the author's name alone.
- Be conservative and prefer UNKNOWN over guessing."""


def normalize_name(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.casefold())


def result_keeps_unknown(result) -> bool:
    value = result.get("keep_unknown", True)
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes"}


def should_apply(result, min_confidence: str):
    if result_keeps_unknown(result):
        return False
    country = normalize_country_value(str(result.get("country", "UNKNOWN")).strip())
    if not country or country == "UNKNOWN":
        return False
    confidence = str(result.get("confidence", "low")).strip().lower()
    return CONFIDENCE_RANK.get(confidence, 0) >= CONFIDENCE_RANK[min_confidence]


def llm_error_response(exc: Exception):
    return {
        "authors": [],
        "error": f"{type(exc).__name__}: {exc}",
    }


def load_first_page_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace").strip()


def write_jsonl(path: Path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=True) + "\n")


def build_paper_authors(paper_authors):
    grouped = defaultdict(list)
    for row in paper_authors:
        grouped[row["paper_id"]].append(row)
    for rows in grouped.values():
        rows.sort(key=lambda row: int(row["author_position"]))
    return dict(grouped)


def fill_unknown_countries_from_title_pages(
    authors,
    paper_authors,
    first_pages_dir: Path,
    config_path: Path | None = None,
    min_confidence: str = "medium",
    paper_limit: int | None = None,
):
    config = load_local_llm_config(config_path)
    updated_authors = [dict(row) for row in authors]
    authors_by_id = {row["author_id"]: row for row in updated_authors}
    paper_authors_by_paper = build_paper_authors(paper_authors)
    retries = int(config.get("retries", 1))
    retry_delay_seconds = float(config.get("retry_delay_seconds", 2))
    progress_every = int(config.get("progress_every", 25))

    pending_papers = []
    for paper_id, links in sorted(paper_authors_by_paper.items()):
        unknown_links = [
            link for link in links if authors_by_id.get(link["author_id"], {}).get("country") == "UNKNOWN"
        ]
        if not unknown_links:
            continue
        first_page_text_path = first_pages_dir / f"{paper_id}.txt"
        if not first_page_text_path.exists():
            continue
        pending_papers.append((paper_id, links, unknown_links, first_page_text_path))

    if paper_limit is not None:
        pending_papers = pending_papers[:paper_limit]

    review_rows = []
    jsonl_rows = []
    applied_updates = 0

    for index, (paper_id, links, unknown_links, first_page_text_path) in enumerate(pending_papers, start=1):
        ordered_authors = [authors_by_id[link["author_id"]] for link in links if link["author_id"] in authors_by_id]
        author_lines = []
        for author in ordered_authors:
            author_lines.append(
                f"- {author['author_name']} | current_institution={author['institution']} | current_country={author['country']}"
            )

        prompt = (
            f"Paper ID: {paper_id}\n"
            f"Authors:\n" + "\n".join(author_lines) + "\n\n"
            f"Full first-page text:\n{load_first_page_text(first_page_text_path)}\n"
        )

        result = None
        for attempt in range(retries + 1):
            try:
                result = ollama_chat_json(
                    [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": prompt},
                    ],
                    config=config,
                )
                break
            except (TimeoutError, socket.timeout, URLError, OSError, ValueError) as exc:
                if attempt >= retries:
                    result = llm_error_response(exc)
                else:
                    time.sleep(retry_delay_seconds)

        author_results = result.get("authors", []) if isinstance(result, dict) else []
        author_results_by_name = {}
        for author_result in author_results:
            key = normalize_name(str(author_result.get("author_name", "")).strip())
            if key and key not in author_results_by_name:
                author_results_by_name[key] = author_result

        jsonl_rows.append(
            {
                "paper_id": paper_id,
                "first_page_text_path": str(first_page_text_path),
                "unknown_author_names": [authors_by_id[link["author_id"]]["author_name"] for link in unknown_links],
                "response": result,
            }
        )

        for link in unknown_links:
            author = authors_by_id[link["author_id"]]
            author_result = author_results_by_name.get(normalize_name(author["author_name"]), {})
            llm_country = normalize_country_value(str(author_result.get("country", "UNKNOWN")).strip())
            applied = should_apply(author_result, min_confidence)
            if applied:
                author["country"] = llm_country
                source_note = author.get("source_note", "").strip()
                if DEFAULT_SOURCE_NOTE not in source_note:
                    author["source_note"] = (
                        f"{source_note}; {DEFAULT_SOURCE_NOTE}" if source_note else DEFAULT_SOURCE_NOTE
                    )
                applied_updates += 1

            review_rows.append(
                {
                    "paper_id": paper_id,
                    "author_id": author["author_id"],
                    "author_name": author["author_name"],
                    "institution": author["institution"],
                    "existing_country": "UNKNOWN",
                    "llm_country": llm_country,
                    "llm_confidence": str(author_result.get("confidence", "low")).strip().lower(),
                    "llm_reason": str(author_result.get("reason", result.get("error", ""))).strip(),
                    "applied": "yes" if applied else "no",
                    "first_page_text_path": str(first_page_text_path),
                }
            )

        if progress_every > 0 and (index % progress_every == 0 or index == len(pending_papers)):
            print(
                f"Processed {index}/{len(pending_papers)} papers with unknown-country authors; "
                f"applied {applied_updates} updates so far",
                flush=True,
            )

    return updated_authors, review_rows, jsonl_rows


def count_applied_updates(review_rows):
    return sum(row["applied"] == "yes" for row in review_rows)


def main():
    parser = argparse.ArgumentParser(
        description="Use a local Ollama model on full first-page text to fill remaining UNKNOWN countries."
    )
    parser.add_argument("--authors-csv", required=True)
    parser.add_argument("--paper-authors-csv", required=True)
    parser.add_argument("--first-pages-dir", required=True)
    parser.add_argument("--output-authors-csv", required=True)
    parser.add_argument("--output-countries-csv", required=True)
    parser.add_argument("--output-review-csv", required=True)
    parser.add_argument("--output-jsonl", required=True)
    parser.add_argument("--config", default=str(Path(__file__).resolve().parent.parent / "config" / "local_llm.json"))
    parser.add_argument("--min-confidence", choices=["low", "medium", "high"], default="medium")
    parser.add_argument("--paper-limit", type=int)
    args = parser.parse_args()

    authors = load_csv(Path(args.authors_csv))
    paper_authors = load_csv(Path(args.paper_authors_csv))
    paper_limit = args.paper_limit if args.paper_limit and args.paper_limit > 0 else None

    updated_authors, review_rows, jsonl_rows = fill_unknown_countries_from_title_pages(
        authors,
        paper_authors,
        Path(args.first_pages_dir),
        config_path=Path(args.config),
        min_confidence=args.min_confidence,
        paper_limit=paper_limit,
    )
    write_csv(Path(args.output_authors_csv), AUTHOR_FIELDS, updated_authors)
    write_csv(Path(args.output_countries_csv), COUNTRY_FIELDS, build_country_rows(updated_authors))
    write_csv(Path(args.output_review_csv), REVIEW_FIELDS, review_rows)
    write_jsonl(Path(args.output_jsonl), jsonl_rows)
    print(
        f"Queried local LLM for {len(jsonl_rows)} papers; "
        f"applied {count_applied_updates(review_rows)} country updates"
    )


if __name__ == "__main__":
    main()
