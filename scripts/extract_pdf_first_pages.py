#!/usr/bin/env python3

import argparse
import csv
import subprocess
import tempfile
import urllib.request
from pathlib import Path


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


def main():
    parser = argparse.ArgumentParser(description="Download paper PDFs and extract first-page text for later affiliation reasoning.")
    parser.add_argument("--papers-index", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--start", type=int, default=0, help="Zero-based start index into papers_index.csv.")
    parser.add_argument("--limit", type=int, default=0, help="Optional limit for partial runs; 0 means all papers.")
    args = parser.parse_args()

    rows = load_rows(Path(args.papers_index))
    if args.start:
        rows = rows[args.start :]
    if args.limit:
        rows = rows[: args.limit]

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest_rows = []

    for row in rows:
        paper_id = row["paper_id"]
        pdf_url = row["pdf_url"]
        txt_path = output_dir / f"{paper_id}.txt"
        status = "ok"
        notes = ""
        try:
            if txt_path.exists() and txt_path.stat().st_size > 0:
                notes = "Skipped download; existing first-page text reused"
            else:
                pdf_bytes = download_bytes(pdf_url)
                txt_path.write_text(first_page_text(pdf_bytes), encoding="utf-8")
        except Exception as exc:
            status = "error"
            notes = str(exc)

        manifest_rows.append(
            {
                "paper_id": paper_id,
                "pdf_url": pdf_url,
                "first_page_text_path": str(txt_path),
                "status": status,
                "notes": notes,
            }
        )
        write_csv(
            Path(args.manifest),
            ["paper_id", "pdf_url", "first_page_text_path", "status", "notes"],
            manifest_rows,
        )

    ok_count = sum(row["status"] == "ok" for row in manifest_rows)
    print(
        f"Extracted first-page text for {ok_count} papers out of {len(manifest_rows)} "
        f"(start={args.start}, limit={args.limit or 'all'})"
    )


if __name__ == "__main__":
    main()
