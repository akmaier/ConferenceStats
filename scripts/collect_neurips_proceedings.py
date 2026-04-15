#!/usr/bin/env python3

import argparse
import csv
import html
import json
import re
import subprocess
import time
from pathlib import Path
from urllib.parse import quote, urljoin


USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/123.0.0.0 Safari/537.36"
)
LEGACY_ENTRY_RE = re.compile(
    r'<li[^>]*>\s*<div class="paper-content">\s*'
    r'<a[^>]+href="([^"]+Abstract[^"]+)">([^<]+)</a>\s*'
    r'<span class="paper-authors">([^<]+)</span>',
    flags=re.S,
)
OPENREVIEW_NOTE_RE = re.compile(
    r'href":"\\/forum\?id=([^"]+)","children":"((?:\\.|[^"])*)".*?'
    r'"items":\[(.*?)\],"maxItems"',
    flags=re.S,
)
OPENREVIEW_AUTHOR_RE = re.compile(
    r'href":"\\/profile\?id=[^"]+","title":"[^"]+","data-toggle":"tooltip","data-placement":"top","children":"((?:\\.|[^"])*)"',
    flags=re.S,
)
OPENREVIEW_HTML_NOTE_RE = re.compile(
    r'<li><div class="note[^"]*"><h4><a href="(/forum\?id=[^"]+)">(.*?)</a></h4>'
    r'<div class="note-authors"><span>(.*?)</span></div>'
    r'<ul class="note-meta-info list-inline">(.*?)</ul>',
    flags=re.S,
)
OPENREVIEW_HTML_AUTHOR_RE = re.compile(r'<a [^>]*href="/profile\?id=[^"]+"[^>]*>([^<]+)</a>')
OPENREVIEW_PAGE_RE = re.compile(r"/submissions\?page=(\d+)(?:&amp;|\\u0026)venue=NeurIPS\.cc%2F2025%2FConference")
OPENREVIEW_FETCH_RETRIES = 6
OPENREVIEW_INITIAL_DELAY_SECONDS = 2.0


def normalize_space(value: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(value)).strip()


def decode_json_string(value: str) -> str:
    return normalize_space(json.loads(f'"{value}"'))


def fetch_url(url: str) -> str:
    delay = OPENREVIEW_INITIAL_DELAY_SECONDS
    last_exc = None
    for attempt in range(OPENREVIEW_FETCH_RETRIES + 1):
        try:
            result = subprocess.run(
                ["curl", "-L", "--fail", "--silent", "-A", USER_AGENT, url],
                check=True,
                capture_output=True,
                text=True,
            )
            return result.stdout
        except subprocess.CalledProcessError as exc:
            last_exc = exc
            if attempt == OPENREVIEW_FETCH_RETRIES:
                raise
            time.sleep(delay)
            delay *= 2
    raise last_exc


def write_csv(path: Path, fieldnames, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def legacy_pdf_url(paper_page_url: str) -> str:
    return (
        paper_page_url
        .replace("/hash/", "/file/")
        .replace("-Abstract", "-Paper")
        .replace(".html", ".pdf")
    )


def parse_legacy_entries(proceedings_url: str, toc_html: str):
    entries = []
    for href, raw_title, raw_authors in LEGACY_ENTRY_RE.findall(toc_html):
        paper_page_url = urljoin(proceedings_url, href)
        author_names = [
            normalize_space(part)
            for part in raw_authors.split(",")
            if normalize_space(part)
        ]
        entries.append(
            {
                "paper_page_url": paper_page_url,
                "pdf_url": legacy_pdf_url(paper_page_url),
                "title": normalize_space(raw_title),
                "author_names": author_names,
            }
        )
    return entries


def parse_openreview_entries(toc_html: str):
    entries = []
    seen_forums = set()
    for href, raw_title, authors_html, meta_html in OPENREVIEW_HTML_NOTE_RE.findall(toc_html):
        if "Published:" not in meta_html:
            continue
        forum_id = href.split("id=", 1)[1]
        if forum_id in seen_forums:
            continue
        seen_forums.add(forum_id)
        author_names = [normalize_space(match) for match in OPENREVIEW_HTML_AUTHOR_RE.findall(authors_html)]
        entries.append(
            {
                "paper_page_url": urljoin("https://openreview.net", href),
                "pdf_url": f"https://openreview.net/pdf?id={forum_id}",
                "title": normalize_space(raw_title),
                "author_names": author_names,
            }
        )

    for forum_id, raw_title, authors_chunk in OPENREVIEW_NOTE_RE.findall(toc_html):
        if forum_id in seen_forums:
            continue
        seen_forums.add(forum_id)
        author_names = [decode_json_string(match) for match in OPENREVIEW_AUTHOR_RE.findall(authors_chunk)]
        entries.append(
            {
                "paper_page_url": f"https://openreview.net/forum?id={forum_id}",
                "pdf_url": f"https://openreview.net/pdf?id={forum_id}",
                "title": decode_json_string(raw_title),
                "author_names": author_names,
            }
        )
    return entries


def extract_openreview_max_page(toc_html: str) -> int:
    pages = [int(match) for match in OPENREVIEW_PAGE_RE.findall(toc_html)]
    return max(pages) if pages else 1


def collect_entries(args, raw_dir: Path):
    if args.year <= 2024:
        toc_html = fetch_url(args.proceedings_url)
        (raw_dir / "toc.html").write_text(toc_html, encoding="utf-8")
        return parse_legacy_entries(args.proceedings_url, toc_html), [args.proceedings_url]

    base_url = f"https://openreview.net/submissions?venue={quote('NeurIPS.cc/2025/Conference', safe='')}"
    entries = []
    seen_pages = []
    max_page = None
    page = 1
    while True:
        page_url = base_url if page == 1 else f"{base_url}&page={page}"
        empty_attempts = 0
        while True:
            toc_html = fetch_url(page_url)
            page_entries = parse_openreview_entries(toc_html)
            if max_page is None:
                max_page = extract_openreview_max_page(toc_html)
            # OpenReview can return a partial app shell or transient block page mid-crawl.
            # Retry a few times before treating an empty page as terminal.
            if page_entries or empty_attempts >= 3 or page >= (max_page or 1):
                break
            empty_attempts += 1
            time.sleep(OPENREVIEW_INITIAL_DELAY_SECONDS * (2 ** empty_attempts))

        seen_pages.append(page_url)
        (raw_dir / f"toc_page_{page:02d}.html").write_text(toc_html, encoding="utf-8")
        if not page_entries and page > (max_page or 1):
            break
        entries.extend(page_entries)
        if args.paper_limit and len(entries) >= args.paper_limit:
            break
        if page >= (max_page or 1):
            break
        page += 1
    return entries, seen_pages


def build_rows(entries, conference: str, year: int):
    papers = []
    paper_authors = []
    authors = []
    paper_index = []
    author_counter = 1

    for paper_counter, entry in enumerate(entries, start=1):
        paper_id = f"{conference.upper()}-{year}-P{paper_counter:04d}"
        author_ids = []
        for position, author_name in enumerate(entry["author_names"], start=1):
            author_id = f"{conference.upper()}-{year}-A{author_counter:06d}"
            author_counter += 1
            author_ids.append(author_id)
            authors.append(
                {
                    "author_id": author_id,
                    "author_name": author_name,
                    "country": "UNKNOWN",
                    "institution": "UNKNOWN",
                    "conference": conference,
                    "year": str(year),
                    "source_url": entry["paper_page_url"],
                    "source_note": "Parsed from NeurIPS proceedings/OpenReview listing; affiliation enrichment pending from PDF first pages",
                }
            )
            paper_authors.append(
                {
                    "paper_id": paper_id,
                    "author_id": author_id,
                    "author_position": str(position),
                }
            )

        papers.append(
            {
                "paper_id": paper_id,
                "title": entry["title"],
                "author_ids": "|".join(author_ids),
                "conference": conference,
                "year": str(year),
                "source_url": entry["paper_page_url"],
            }
        )
        paper_index.append(
            {
                "paper_id": paper_id,
                "title": entry["title"],
                "paper_page_url": entry["paper_page_url"],
                "pdf_url": entry["pdf_url"],
            }
        )

    return authors, papers, paper_authors, paper_index


def write_collection_notes(path: Path, conference: str, year: int, source_urls, paper_count: int, author_count: int, paper_limit: int):
    source_lines = "\n".join(f"- {url}" for url in source_urls)
    scope_line = (
        f"- collection limited to the first {paper_limit} papers for workflow probing"
        if paper_limit
        else "- all reachable proceedings pages parsed"
    )
    text = f"""# {conference} {year} Collection Notes

- Conference: {conference}
- Year: {year}
- Collection status: script-generated proceedings metadata

## Source Pages

{source_lines}

## Scope

This dataset was generated by `scripts/collect_neurips_proceedings.py`.

Included in this run:

{scope_line}
- paper titles and ordered author lists from NeurIPS proceedings/OpenReview pages
- paper page URLs and PDF URLs in `papers_index.csv`

## Counts

- Papers collected: {paper_count}
- Author records collected: {author_count}
"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="Collect NeurIPS proceedings metadata into normalized CSVs.")
    parser.add_argument("--conference", required=True)
    parser.add_argument("--conference-slug", required=True)
    parser.add_argument("--year", required=True, type=int)
    parser.add_argument("--proceedings-url", required=True)
    parser.add_argument("--raw-dir", required=True)
    parser.add_argument("--normalized-dir", required=True)
    parser.add_argument("--paper-limit", type=int, default=0)
    args = parser.parse_args()

    raw_dir = Path(args.raw_dir)
    normalized_dir = Path(args.normalized_dir)
    raw_dir.mkdir(parents=True, exist_ok=True)
    normalized_dir.mkdir(parents=True, exist_ok=True)

    entries, source_urls = collect_entries(args, raw_dir)
    if args.paper_limit:
        entries = entries[: args.paper_limit]
    authors, papers, paper_authors, paper_index = build_rows(entries, args.conference, args.year)

    write_csv(
        normalized_dir / "authors.csv",
        ["author_id", "author_name", "country", "institution", "conference", "year", "source_url", "source_note"],
        authors,
    )
    write_csv(
        normalized_dir / "papers.csv",
        ["paper_id", "title", "author_ids", "conference", "year", "source_url"],
        papers,
    )
    write_csv(
        normalized_dir / "paper_authors.csv",
        ["paper_id", "author_id", "author_position"],
        paper_authors,
    )
    write_csv(
        raw_dir / "papers_index.csv",
        ["paper_id", "title", "paper_page_url", "pdf_url"],
        paper_index,
    )
    write_csv(
        raw_dir / "source_manifest.csv",
        ["source_url", "source_type", "used_for", "notes"],
        [
            {
                "source_url": url,
                "source_type": "neurips_proceedings_page" if args.year <= 2024 else "openreview_submissions_page",
                "used_for": "paper titles, author order, paper page URLs, PDF URLs",
                "notes": "Primary source for NeurIPS proceedings metadata",
            }
            for url in source_urls
        ],
    )
    write_collection_notes(
        raw_dir / "collection_notes.md",
        args.conference,
        args.year,
        source_urls,
        len(papers),
        len(authors),
        args.paper_limit,
    )

    print(f"Collected {len(papers)} papers and {len(authors)} author records")


if __name__ == "__main__":
    main()
