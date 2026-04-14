#!/usr/bin/env python3

import argparse
import socket
import time
from pathlib import Path
from urllib.error import URLError

try:
    from affiliation_pipeline import AUTHOR_FIELDS, load_csv, normalize_country_value, write_csv
    from local_llm import load_local_llm_config, ollama_chat_json
except ModuleNotFoundError:
    from scripts.affiliation_pipeline import AUTHOR_FIELDS, load_csv, normalize_country_value, write_csv
    from scripts.local_llm import load_local_llm_config, ollama_chat_json

REVIEW_FIELDS = [
    "author_id",
    "author_name",
    "institution",
    "existing_country",
    "llm_country",
    "llm_confidence",
    "llm_reason",
    "applied",
]

CONFIDENCE_RANK = {"low": 1, "medium": 2, "high": 3}
DEFAULT_SOURCE_NOTE = "Country inferred from institution using local Ollama model"

SYSTEM_PROMPT = """You infer countries from institution names.
Return only JSON with keys:
- country: a country name, a ` | `-separated list of country names, or UNKNOWN
- confidence: high, medium, or low
- reason: short explanation
- keep_unknown: true if the country cannot be determined reliably
Rules:
- Use the institution string as the main evidence.
- Use canonical country names such as `United States`, `United Kingdom`, `South Korea`, `China`, `Taiwan`.
- If multiple institutions are present and belong to multiple countries, return a ` | `-separated list.
- If the institution is ambiguous, incomplete, or could reasonably map to more than one country, set keep_unknown to true.
- Never use the author's name as evidence.
- Be conservative."""


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


def llm_error_result(exc: Exception):
    return {
        "country": "UNKNOWN",
        "confidence": "low",
        "reason": f"local_llm_error: {type(exc).__name__}: {exc}",
        "keep_unknown": True,
    }


def fill_unknown_countries_with_local_llm(authors, config_path: Path | None = None, min_confidence: str = "medium", limit: int | None = None):
    config = load_local_llm_config(config_path)
    updated_authors = [dict(row) for row in authors]
    authors_by_id = {row["author_id"]: row for row in updated_authors}
    review_rows = []
    retries = int(config.get("retries", 1))
    retry_delay_seconds = float(config.get("retry_delay_seconds", 2))
    progress_every = int(config.get("progress_every", 25))

    pending = [
        row
        for row in updated_authors
        if row["institution"] != "UNKNOWN" and row["country"] == "UNKNOWN"
    ]
    if limit is not None:
        pending = pending[:limit]

    pending_by_institution = {}
    institution_order = []
    for row in pending:
        institution = row["institution"]
        if institution not in pending_by_institution:
            pending_by_institution[institution] = []
            institution_order.append(institution)
        pending_by_institution[institution].append(row)

    applied_updates = 0
    for index, institution in enumerate(institution_order, start=1):
        sample_row = pending_by_institution[institution][0]
        prompt = (
            f"Infer the country from this institution string.\n"
            f"Institution: {institution}\n"
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
                    result = llm_error_result(exc)
                else:
                    time.sleep(retry_delay_seconds)

        llm_country = normalize_country_value(str(result.get("country", "UNKNOWN")).strip())
        applied = should_apply(result, min_confidence)

        for row in pending_by_institution[institution]:
            existing_country = row["country"]
            row_applied = applied
            if row_applied:
                authors_by_id[row["author_id"]]["country"] = llm_country
                source_note = authors_by_id[row["author_id"]].get("source_note", "").strip()
                if DEFAULT_SOURCE_NOTE not in source_note:
                    if source_note:
                        source_note = f"{source_note}; {DEFAULT_SOURCE_NOTE}"
                    else:
                        source_note = DEFAULT_SOURCE_NOTE
                    authors_by_id[row["author_id"]]["source_note"] = source_note
                applied_updates += 1

            review_rows.append(
                {
                    "author_id": row["author_id"],
                    "author_name": row["author_name"],
                    "institution": row["institution"],
                    "existing_country": existing_country,
                    "llm_country": llm_country,
                    "llm_confidence": str(result.get("confidence", "low")).strip().lower(),
                    "llm_reason": str(result.get("reason", "")).strip(),
                    "applied": "yes" if row_applied else "no",
                }
            )

        if progress_every > 0 and (index % progress_every == 0 or index == len(institution_order)):
            print(
                f"Processed {index}/{len(institution_order)} unique institution prompts; "
                f"applied {applied_updates} updates so far",
                flush=True,
            )

    return updated_authors, review_rows


def count_applied_updates(review_rows):
    return sum(row["applied"] == "yes" for row in review_rows)


def main():
    parser = argparse.ArgumentParser(description="Use a local Ollama model to fill UNKNOWN countries from institution strings.")
    parser.add_argument("--authors-csv", required=True)
    parser.add_argument("--output-authors-csv", required=True)
    parser.add_argument("--output-review-csv", required=True)
    parser.add_argument("--config", default=str(Path(__file__).resolve().parent.parent / "config" / "local_llm.json"))
    parser.add_argument("--min-confidence", choices=["low", "medium", "high"], default="medium")
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()

    authors = load_csv(Path(args.authors_csv))
    updated_authors, review_rows = fill_unknown_countries_with_local_llm(
        authors,
        config_path=Path(args.config),
        min_confidence=args.min_confidence,
        limit=args.limit,
    )
    write_csv(Path(args.output_authors_csv), AUTHOR_FIELDS, updated_authors)
    write_csv(Path(args.output_review_csv), REVIEW_FIELDS, review_rows)
    print(
        f"Queried local LLM for {len(review_rows)} author rows; "
        f"applied {count_applied_updates(review_rows)} country updates"
    )


if __name__ == "__main__":
    main()
