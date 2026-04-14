#!/usr/bin/env python3

import argparse
import csv
import html
import re
import urllib.request
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin


BOOK_PAGE_RE = re.compile(r'href="[^"]+\?page=(\d+)#toc"')


def normalize_space(value: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(value)).strip()


def fetch_url(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": "ConferenceStats/1.0"})
    with urllib.request.urlopen(request, timeout=60) as response:
        return response.read().decode("utf-8", errors="replace")


def write_csv(path: Path, fieldnames, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


class SpringerTocParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.entries = []
        self._chapter_depth = 0
        self._chapter = None
        self._title_depth = 0
        self._author_list_depth = 0
        self._author_item_depth = 0
        self._page_depth = 0

    def handle_starttag(self, tag, attrs):
        attr_map = dict(attrs)
        data_test = attr_map.get("data-test", "")
        classes = set(attr_map.get("class", "").split())

        if tag == "li" and data_test == "chapter":
            if self._chapter_depth == 0:
                self._chapter = {
                    "title_parts": [],
                    "paper_page_url": "",
                    "pdf_url": "",
                    "authors_parts": [],
                    "pages_parts": [],
                }
            self._chapter_depth += 1
            return

        if self._chapter_depth == 0:
            return

        if tag == "li":
            self._chapter_depth += 1

        if tag in {"h3", "h4"} and data_test.startswith("chapter-title-"):
            self._title_depth += 1
        elif tag == "a" and self._title_depth and not self._chapter["paper_page_url"]:
            self._chapter["paper_page_url"] = attr_map.get("href", "")

        if tag == "ul" and "app-author-list" in classes:
            self._author_list_depth += 1
        elif tag == "li" and self._author_list_depth and "app-author-list__item" in classes:
            self._author_item_depth += 1

        if tag == "span" and data_test == "page-number":
            self._page_depth += 1

        if tag == "a" and data_test == "chapter-pdf":
            self._chapter["pdf_url"] = attr_map.get("href", "")

    def handle_endtag(self, tag):
        if self._chapter_depth == 0:
            return

        if tag in {"h3", "h4"} and self._title_depth:
            self._title_depth -= 1

        if tag == "span" and self._page_depth:
            self._page_depth -= 1

        if tag == "li" and self._author_item_depth:
            self._author_item_depth -= 1
        elif tag == "ul" and self._author_list_depth:
            self._author_list_depth -= 1

        if tag == "li":
            self._chapter_depth -= 1
            if self._chapter_depth == 0 and self._chapter is not None:
                entry = {
                    "title": normalize_space("".join(self._chapter["title_parts"])),
                    "paper_page_url": self._chapter["paper_page_url"],
                    "pdf_url": self._chapter["pdf_url"],
                    "authors_text": normalize_space("".join(self._chapter["authors_parts"])),
                    "pages": normalize_space("".join(self._chapter["pages_parts"])),
                }
                if entry["title"] and entry["title"].lower() != "front matter":
                    self.entries.append(entry)
                self._chapter = None

    def handle_data(self, data):
        if self._chapter_depth == 0 or self._chapter is None:
            return
        if self._title_depth:
            self._chapter["title_parts"].append(data)
        if self._author_item_depth:
            self._chapter["authors_parts"].append(data)
        if self._page_depth:
            self._chapter["pages_parts"].append(data)


class SpringerOtherVolumesParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.entries = []
        self._inside_other_volumes = False
        self._other_volumes_depth = 0
        self._current_href = ""
        self._current_text_parts = []
        self._capture_text = False

    def handle_starttag(self, tag, attrs):
        attr_map = dict(attrs)
        if tag == "ol" and attr_map.get("id") == "other-volumes":
            self._inside_other_volumes = True
            self._other_volumes_depth = 1
            return

        if not self._inside_other_volumes:
            return

        if tag == "ol":
            self._other_volumes_depth += 1

        if tag == "a":
            href = attr_map.get("href", "")
            if href.startswith("/book/"):
                self._current_href = href
                self._current_text_parts = []
                self._capture_text = True

    def handle_endtag(self, tag):
        if not self._inside_other_volumes:
            return

        if tag == "a" and self._capture_text:
            text = normalize_space("".join(self._current_text_parts))
            if self._current_href:
                self.entries.append({"href": self._current_href, "text": text})
            self._current_href = ""
            self._current_text_parts = []
            self._capture_text = False
            return

        if tag == "ol":
            self._other_volumes_depth -= 1
            if self._other_volumes_depth == 0:
                self._inside_other_volumes = False

    def handle_data(self, data):
        if self._capture_text:
            self._current_text_parts.append(data)


def parse_toc_entries(base_url: str, toc_html: str):
    parser = SpringerTocParser()
    parser.feed(toc_html)
    entries = []
    for entry in parser.entries:
        authors_text = entry["authors_text"]
        author_names = [normalize_space(name) for name in authors_text.split(",") if normalize_space(name)]
        entries.append(
            {
                "title": entry["title"],
                "author_names": author_names,
                "paper_page_url": urljoin(base_url, entry["paper_page_url"]),
                "pdf_url": urljoin(base_url, entry["pdf_url"]),
                "pages": entry["pages"],
            }
        )
    return entries


def page_urls_for_volume(base_url: str, landing_html: str):
    pages = {1}
    for page_number in BOOK_PAGE_RE.findall(landing_html):
        pages.add(int(page_number))
    return [
        base_url if page_number == 1 else f"{base_url}?page={page_number}#toc"
        for page_number in sorted(pages)
    ]


def discover_related_volumes(base_url: str, landing_html: str):
    parser = SpringerOtherVolumesParser()
    parser.feed(landing_html)

    discovered = [base_url]
    seen = {base_url}
    for entry in parser.entries:
        text = entry["text"]
        if "workshop" in text.lower():
            continue
        full_url = urljoin(base_url, entry["href"])
        if full_url not in seen:
            seen.add(full_url)
            discovered.append(full_url)
    return discovered


def read_volumes_csv(path: Path):
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    volumes = []
    for index, row in enumerate(rows, start=1):
        proceedings_url = row.get("proceedings_url", "").strip()
        if not proceedings_url:
            continue
        volumes.append(
            {
                "volume_label": row.get("volume_label", "").strip() or f"volume_{index:02d}",
                "proceedings_url": proceedings_url,
                "notes": row.get("notes", "").strip(),
            }
        )
    return volumes


def collect_entries(volumes, raw_dir: Path):
    all_entries = []
    source_rows = []

    for volume_index, volume in enumerate(volumes, start=1):
        proceedings_url = volume["proceedings_url"]
        landing_html = fetch_url(proceedings_url)
        volume_dir = raw_dir / "toc_pages" / volume["volume_label"]
        volume_dir.mkdir(parents=True, exist_ok=True)
        (volume_dir / "page_01.html").write_text(landing_html, encoding="utf-8")

        seen_page_urls = set()
        for page_index, page_url in enumerate(page_urls_for_volume(proceedings_url, landing_html), start=1):
            if page_url in seen_page_urls:
                continue
            seen_page_urls.add(page_url)
            toc_html = landing_html if page_index == 1 else fetch_url(page_url)
            (volume_dir / f"page_{page_index:02d}.html").write_text(toc_html, encoding="utf-8")
            all_entries.extend(parse_toc_entries(proceedings_url, toc_html))

        source_rows.append(
            {
                "source_url": proceedings_url,
                "source_type": "springer_book_toc",
                "used_for": "chapter titles, author list preview, chapter page URLs, chapter PDF URLs",
                "notes": volume["notes"] or f"Volume {volume['volume_label']}",
            }
        )

    return all_entries, source_rows


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
                    "source_note": "Parsed from Springer proceedings TOC; affiliations require first-page enrichment and author lists may be truncated with et al.",
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


def write_collection_notes(path: Path, conference: str, year: int, volumes, paper_count: int, author_count: int):
    volume_lines = "\n".join(
        f"- `{volume['volume_label']}`: {volume['proceedings_url']}" for volume in volumes
    )
    text = f"""# {conference} {year} Collection Notes

- Conference: {conference}
- Year: {year}
- Collection status: script-generated Springer proceedings metadata

## Volumes Used

{volume_lines}

## Scope

This dataset was generated by `scripts/collect_springer_proceedings.py`.

Included in this run:

- Springer table-of-contents parsing across the listed volume pages
- chapter titles
- chapter page URLs and PDF URLs in the raw index
- author list preview text from the TOC

Not yet included:

- full affiliation and country enrichment from first-page text
- recovery of authors omitted from Springer TOC previews that use `et al.`

## Counts

- Papers collected: {paper_count}
- Author records collected: {author_count}
"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="Collect Springer proceedings metadata into normalized CSVs.")
    parser.add_argument("--conference", required=True)
    parser.add_argument("--conference-slug", required=True)
    parser.add_argument("--year", required=True, type=int)
    parser.add_argument("--raw-dir", required=True)
    parser.add_argument("--normalized-dir", required=True)
    parser.add_argument("--proceedings-url", action="append", default=[])
    parser.add_argument("--volumes-csv")
    args = parser.parse_args()

    raw_dir = Path(args.raw_dir)
    normalized_dir = Path(args.normalized_dir)
    raw_dir.mkdir(parents=True, exist_ok=True)
    normalized_dir.mkdir(parents=True, exist_ok=True)

    volumes = []
    if args.volumes_csv:
        volumes.extend(read_volumes_csv(Path(args.volumes_csv)))
    if not volumes and args.proceedings_url:
        seed_urls = list(args.proceedings_url)
        expanded_urls = []
        seen_urls = set()
        for proceedings_url in seed_urls:
            landing_html = fetch_url(proceedings_url)
            for discovered_url in discover_related_volumes(proceedings_url, landing_html):
                if discovered_url not in seen_urls:
                    seen_urls.add(discovered_url)
                    expanded_urls.append(discovered_url)
        for index, proceedings_url in enumerate(expanded_urls, start=1):
            volumes.append(
                {
                    "volume_label": f"volume_{index:02d}",
                    "proceedings_url": proceedings_url,
                    "notes": "Auto-discovered from Springer other-volumes list",
                }
            )
    elif args.proceedings_url:
        for index, proceedings_url in enumerate(args.proceedings_url, start=1):
            volumes.append(
                {
                    "volume_label": f"volume_{index:02d}",
                    "proceedings_url": proceedings_url,
                    "notes": "",
                }
            )
    if not volumes:
        raise SystemExit("Provide at least one --proceedings-url or a --volumes-csv file")

    entries, source_rows = collect_entries(volumes, raw_dir)
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
    write_collection_notes(
        raw_dir / "collection_notes.md",
        args.conference,
        args.year,
        volumes,
        len(papers),
        len(authors),
    )

    print(f"Collected {len(papers)} papers and {len(authors)} author records")


if __name__ == "__main__":
    main()
