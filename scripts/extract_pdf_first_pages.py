#!/usr/bin/env python3

import argparse
import csv
import subprocess
import tempfile
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import urljoin


def load_rows(path: Path):
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, fieldnames, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def download_bytes(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "ConferenceStats/1.0"})
    with urllib.request.urlopen(request, timeout=60) as response:
        return response.read()


def fetch_text(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": "ConferenceStats/1.0"})
    with urllib.request.urlopen(request, timeout=60) as response:
        return response.read().decode("utf-8", errors="replace")


def derived_pdf_url_from_paper_page(paper_page_url: str) -> str:
    if not paper_page_url:
        return ""
    return (
        paper_page_url
        .replace("/html/", "/papers/")
        .replace("_paper.html", "_paper.pdf")
    )


def discover_pdf_url_from_paper_page(paper_page_url: str) -> str:
    if not paper_page_url:
        return ""
    html = fetch_text(paper_page_url)
    marker = "_paper.pdf"
    href_index = html.find(marker)
    if href_index < 0:
        return ""
    start_index = html.rfind('href="', 0, href_index)
    if start_index < 0:
        return ""
    start_index += len('href="')
    return urljoin(paper_page_url, html[start_index:href_index + len(marker)])


def initial_pdf_candidate_urls(row) -> list[str]:
    candidates = []
    for candidate in [
        row.get("pdf_url", ""),
        derived_pdf_url_from_paper_page(row.get("paper_page_url", "")),
    ]:
        if candidate and candidate not in candidates:
            candidates.append(candidate)
    return candidates


def first_page_text(pdf_bytes: bytes) -> str:
    with tempfile.NamedTemporaryFile(suffix=".pdf") as handle:
        handle.write(pdf_bytes)
        handle.flush()
        result = subprocess.run(
            ["pdftotext", "-f", "1", "-l", "1", handle.name, "-"],
            check=True,
            capture_output=True,
            text=True,
        )
        return result.stdout


def process_row(row, output_dir: Path):
    paper_id = row["paper_id"]
    pdf_url = row["pdf_url"]
    txt_path = output_dir / f"{paper_id}.txt"
    status = "ok"
    notes = ""

    try:
        if txt_path.exists() and txt_path.stat().st_size > 0:
            notes = "Skipped download; existing first-page text reused"
        else:
            last_error = None
            chosen_pdf_url = pdf_url
            tried_urls = initial_pdf_candidate_urls(row)

            for candidate_url in tried_urls:
                try:
                    pdf_bytes = download_bytes(candidate_url)
                    txt_path.write_text(first_page_text(pdf_bytes), encoding="utf-8")
                    chosen_pdf_url = candidate_url
                    last_error = None
                    break
                except Exception as exc:
                    last_error = exc

            if last_error is not None:
                discovered_url = discover_pdf_url_from_paper_page(row.get("paper_page_url", ""))
                if discovered_url and discovered_url not in tried_urls:
                    pdf_bytes = download_bytes(discovered_url)
                    txt_path.write_text(first_page_text(pdf_bytes), encoding="utf-8")
                    chosen_pdf_url = discovered_url
                    last_error = None

            if last_error is not None:
                raise last_error

            pdf_url = chosen_pdf_url
    except Exception as exc:
        status = "error"
        notes = str(exc)

    return {
        "paper_id": paper_id,
        "pdf_url": pdf_url,
        "first_page_text_path": str(txt_path),
        "status": status,
        "notes": notes,
    }


def main():
    parser = argparse.ArgumentParser(description="Download paper PDFs and extract first-page text for later affiliation reasoning.")
    parser.add_argument("--papers-index", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--start", type=int, default=0, help="Zero-based start index into papers_index.csv.")
    parser.add_argument("--limit", type=int, default=0, help="Optional limit for partial runs; 0 means all papers.")
    parser.add_argument("--workers", type=int, default=4, help="Number of concurrent first-page extraction workers.")
    parser.add_argument(
        "--manifest-flush-every",
        type=int,
        default=0,
        help="Rewrite the manifest after this many completed papers; 0 defaults to the worker count.",
    )
    args = parser.parse_args()

    rows = load_rows(Path(args.papers_index))
    if args.start:
        rows = rows[args.start :]
    if args.limit:
        rows = rows[: args.limit]

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    workers = max(1, args.workers)
    manifest_flush_every = max(1, args.manifest_flush_every or workers)

    completed_rows = {}
    completed_since_flush = 0
    total_rows = len(rows)

    with ThreadPoolExecutor(max_workers=workers) as executor:
        future_to_index = {
            executor.submit(process_row, row, output_dir): index
            for index, row in enumerate(rows)
        }

        for future in as_completed(future_to_index):
            index = future_to_index[future]
            completed_rows[index] = future.result()
            completed_since_flush += 1

            if completed_since_flush >= manifest_flush_every or len(completed_rows) == total_rows:
                ordered_rows = [completed_rows[i] for i in sorted(completed_rows)]
                write_csv(
                    Path(args.manifest),
                    ["paper_id", "pdf_url", "first_page_text_path", "status", "notes"],
                    ordered_rows,
                )
                completed_since_flush = 0

    ordered_rows = [completed_rows[i] for i in sorted(completed_rows)]
    ok_count = sum(row["status"] == "ok" for row in ordered_rows)
    print(
        f"Extracted first-page text for {ok_count} papers out of {len(ordered_rows)} "
        f"(start={args.start}, limit={args.limit or 'all'}, workers={workers})"
    )


if __name__ == "__main__":
    main()
