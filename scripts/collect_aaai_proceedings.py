#!/usr/bin/env python3

import argparse
import csv
import html
import re
import subprocess
from pathlib import Path
from urllib.parse import urljoin


USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/123.0.0.0 Safari/537.36"
)
TRACK_LINK_RE = re.compile(r"<li>\s*<a href=\"([^\"]+)\"[^>]*>(.*?)</a>\s*</li>", flags=re.I | re.S)
AAAI_PAPER_RE = re.compile(
    r'<li class="paper-wrap">.*?<h5><a href="([^"]+)">(.*?)</a></h5>'
    r'.*?<span class="papers-author-page"><p>(.*?)</p>'
    r'.*?<a class="wp-block-button"[^>]*href="([^"]+)"',
    flags=re.S,
)
OJS_PAPER_RE = re.compile(
    r'<div class="obj_article_summary">.*?<h3 class="title">\s*<a[^>]+href="([^"]+)">\s*(.*?)\s*</a>'
    r'.*?<div class="authors">\s*(.*?)\s*</div>'
    r'.*?<a class="obj_galley_link pdf" href="([^"]+)"',
    flags=re.S,
)


def normalize_space(value: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(value)).strip()


def fetch_url(url: str) -> str:
    result = subprocess.run(
        ["curl", "-L", "--fail", "--silent", "-A", USER_AGENT, url],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout


def write_csv(path: Path, fieldnames, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def include_track(label: str) -> bool:
    lowered = label.casefold()
    if lowered.startswith("skip to "):
        return False
    if "aaai" in lowered and not any(
        term in lowered
        for term in ["student", "undergraduate", "demonstration", "demonstrations", "doctoral consortium"]
    ):
        return True
    excluded_terms = [
        "innovative applications",
        "iaai",
        "eaai",
        "student",
        "undergraduate",
        "demonstration",
        "demonstrations",
        "doctoral consortium",
    ]
    return not any(term in lowered for term in excluded_terms)


def discover_track_pages(proceedings_url: str, landing_html: str):
    tracks = []
    seen = set()
    for href, label in TRACK_LINK_RE.findall(landing_html):
        normalized_label = normalize_space(label)
        full_url = urljoin(proceedings_url, href)
        if href.startswith("#"):
            continue
        if not include_track(normalized_label) or full_url in seen:
            continue
        seen.add(full_url)
        tracks.append({"track_label": normalized_label, "track_url": full_url})
    if not tracks and AAAI_PAPER_RE.search(landing_html):
        tracks.append({"track_label": "Landing Page Papers", "track_url": proceedings_url})
    return tracks


def parse_aaai_page_entries(track_url: str, page_html: str):
    entries = []
    for paper_page_url, raw_title, raw_authors, pdf_url in AAAI_PAPER_RE.findall(page_html):
        author_names = [
            normalize_space(part)
            for part in raw_authors.split(",")
            if normalize_space(part)
        ]
        entries.append(
            {
                "paper_page_url": urljoin(track_url, paper_page_url),
                "pdf_url": urljoin(track_url, pdf_url),
                "title": normalize_space(raw_title),
                "author_names": author_names,
            }
        )
    return entries


def parse_ojs_entries(track_url: str, page_html: str):
    entries = []
    for paper_page_url, raw_title, raw_authors, pdf_url in OJS_PAPER_RE.findall(page_html):
        author_names = [
            normalize_space(part)
            for part in raw_authors.split(",")
            if normalize_space(part)
        ]
        entries.append(
            {
                "paper_page_url": urljoin(track_url, paper_page_url),
                "pdf_url": urljoin(track_url, pdf_url),
                "title": normalize_space(raw_title),
                "author_names": author_names,
            }
        )
    return entries


def collect_entries(args, raw_dir: Path):
    landing_html = fetch_url(args.proceedings_url)
    (raw_dir / "toc.html").write_text(landing_html, encoding="utf-8")

    tracks = discover_track_pages(args.proceedings_url, landing_html)
    if args.track_limit:
        tracks = tracks[: args.track_limit]

    entries = []
    source_rows = [
        {
            "source_url": args.proceedings_url,
            "source_type": "aaai_proceedings_landing_page",
            "used_for": "sub-track discovery",
            "notes": "AAAI proceedings landing page that links to track pages or OJS issues",
        }
    ]
    seen_papers = set()

    for index, track in enumerate(tracks, start=1):
        track_html = landing_html if track["track_url"] == args.proceedings_url else fetch_url(track["track_url"])
        (raw_dir / f"track_{index:02d}.html").write_text(track_html, encoding="utf-8")
        parsed_entries = parse_ojs_entries(track["track_url"], track_html) if "ojs.aaai.org" in track["track_url"] else parse_aaai_page_entries(track["track_url"], track_html)
        for entry in parsed_entries:
            key = entry["paper_page_url"] or entry["title"]
            if key in seen_papers:
                continue
            seen_papers.add(key)
            entries.append(entry)
            if args.paper_limit and len(entries) >= args.paper_limit:
                break
        source_rows.append(
            {
                "source_url": track["track_url"],
                "source_type": "aaai_track_page" if "ojs.aaai.org" not in track["track_url"] else "aaai_ojs_issue_page",
                "used_for": "paper titles, author order, paper page URLs, PDF URLs",
                "notes": track["track_label"],
            }
        )
        if args.paper_limit and len(entries) >= args.paper_limit:
            break

    return entries, tracks, source_rows


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
                    "source_note": "Parsed from AAAI track pages or OJS issues; affiliation enrichment pending from PDF first pages",
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


def write_collection_notes(path: Path, conference: str, year: int, tracks, paper_count: int, author_count: int, paper_limit: int, track_limit: int):
    track_lines = "\n".join(f"- `{track['track_label']}`: {track['track_url']}" for track in tracks)
    scope_lines = []
    if track_limit:
        scope_lines.append(f"- limited to the first {track_limit} discovered track pages for workflow probing")
    if paper_limit:
        scope_lines.append(f"- limited to the first {paper_limit} papers after track expansion")
    if not scope_lines:
        scope_lines.append("- all discovered main-conference track pages parsed")
    text = f"""# {conference} {year} Collection Notes

- Conference: {conference}
- Year: {year}
- Collection status: script-generated proceedings metadata

## Track Pages Used

{track_lines}

## Scope

This dataset was generated by `scripts/collect_aaai_proceedings.py`.

Included in this run:

{chr(10).join(scope_lines)}
- landing-page sub-track discovery
- paper titles and ordered author lists from the discovered track pages
- paper page URLs and PDF URLs in `papers_index.csv`

## Counts

- Papers collected: {paper_count}
- Author records collected: {author_count}
"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="Collect AAAI proceedings metadata into normalized CSVs.")
    parser.add_argument("--conference", required=True)
    parser.add_argument("--conference-slug", required=True)
    parser.add_argument("--year", required=True, type=int)
    parser.add_argument("--proceedings-url", required=True)
    parser.add_argument("--raw-dir", required=True)
    parser.add_argument("--normalized-dir", required=True)
    parser.add_argument("--paper-limit", type=int, default=0)
    parser.add_argument("--track-limit", type=int, default=0)
    args = parser.parse_args()

    raw_dir = Path(args.raw_dir)
    normalized_dir = Path(args.normalized_dir)
    raw_dir.mkdir(parents=True, exist_ok=True)
    normalized_dir.mkdir(parents=True, exist_ok=True)

    entries, tracks, source_rows = collect_entries(args, raw_dir)
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
        source_rows,
    )
    write_csv(
        raw_dir / "proceedings_tracks.csv",
        ["track_label", "track_url"],
        tracks,
    )
    write_collection_notes(
        raw_dir / "collection_notes.md",
        args.conference,
        args.year,
        tracks,
        len(papers),
        len(authors),
        args.paper_limit,
        args.track_limit,
    )

    print(f"Collected {len(papers)} papers and {len(authors)} author records")


if __name__ == "__main__":
    main()
