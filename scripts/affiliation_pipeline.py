#!/usr/bin/env python3

import csv
import re
from collections import defaultdict
from pathlib import Path


COUNTRY_PATTERNS = [
    ("South Korea", ["south korea", "seoul, korea", " seoul korea", "seoul national university", "korea"]),
    ("North Korea", ["north korea"]),
    (
        "United States",
        [
            "united states",
            "usa",
            "carnegie mellon",
            "university of michigan",
            "ann arbor",
            "north carolina",
            "chapel hill",
            "mit media lab",
            "disney research pittsburgh",
            "pittsburgh",
            "duke university",
            "university of illinois",
            "university of california, san diego",
            "uc berkeley",
            "berkeley",
            "northeastern university",
            "boston, ma",
            "google inc",
            "magic leap",
            "university of maryland",
            "college park",
        ],
    ),
    ("United Kingdom", ["united kingdom", "uk"]),
    ("Germany", ["germany", "universitat bonn", "rheinische friedrich-wilhelms-universitat bonn", "leibniz university hannover", "hannover"]),
    ("France", ["france", "saint-etienne"]),
    ("Netherlands", ["netherlands", "amsterdam"]),
    ("Taiwan", ["taiwan", "academia sinica", "national taiwan university"]),
    ("China", ["china", "chinese academy", "electronic science and technology of china"]),
    ("Australia", ["australia", "adelaide", "queensland", "robotic vision", "western australia", "crawley"]),
    ("Canada", ["canada"]),
    ("Japan", ["japan"]),
    ("Singapore", ["singapore"]),
    ("Switzerland", ["switzerland"]),
    ("Italy", ["italy"]),
    ("Spain", ["spain"]),
    ("Israel", ["israel"]),
    ("South Korea", ["unist"]),
]

COUNTRY_ALIASES = {
    "usa": "United States",
    "u.s.a.": "United States",
    "u.s.": "United States",
    "united states": "United States",
    "united states of america": "United States",
    "uk": "United Kingdom",
    "u.k.": "United Kingdom",
    "great britain": "United Kingdom",
    "england": "United Kingdom",
    "republic of korea": "South Korea",
    "korea, republic of": "South Korea",
    "south korea": "South Korea",
    "republic of china": "Taiwan",
    "taiwan, republic of china": "Taiwan",
    "people's republic of china": "China",
    "peoples republic of china": "China",
    "pr china": "China",
    "prc": "China",
}

PARSE_SOURCE_NOTE = "Affiliation parsed from local first-page text extracted from paper PDF"
VARIANT_PRIORITY = {"numbered": 0, "symbol": 1, "stacked": 2, "shared": 3}
MIN_AFFILIATION_SCORE = 2

AUTHOR_FIELDS = [
    "author_id",
    "author_name",
    "country",
    "institution",
    "conference",
    "year",
    "source_url",
    "source_note",
]

CANDIDATE_FIELDS = [
    "paper_id",
    "author_id",
    "author_name",
    "variant",
    "variant_priority",
    "variant_coverage",
    "author_count",
    "institution_candidate",
    "candidate_score",
    "first_page_text_path",
    "source_url",
]

LINK_FIELDS = [
    "paper_id",
    "author_id",
    "author_name",
    "selected_variant",
    "selection_reason",
    "institution_raw",
    "candidate_score",
    "first_page_text_path",
    "source_url",
]

INSTITUTION_FIELDS = [
    "paper_id",
    "author_id",
    "author_name",
    "selected_variant",
    "selection_reason",
    "institution_raw",
    "institution_normalized",
    "candidate_score",
    "first_page_text_path",
    "source_url",
]

COUNTRY_FIELDS = [
    "author_id",
    "author_name",
    "institution",
    "country",
    "conference",
    "year",
]


def load_csv(path: Path):
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, fieldnames, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def normalize_space(value: str) -> str:
    value = value.replace("\u00a0", " ")
    return re.sub(r"\s+", " ", value).strip()


def normalize_country_name(value: str) -> str:
    cleaned = normalize_space(str(value)).strip(" ,;")
    if not cleaned:
        return "UNKNOWN"
    lowered = cleaned.casefold()
    if lowered == "unknown":
        return "UNKNOWN"
    return COUNTRY_ALIASES.get(lowered, cleaned)


def normalize_country_value(value: str) -> str:
    normalized = []
    for part in str(value).split("|"):
        country = normalize_country_name(part)
        if country == "UNKNOWN":
            continue
        if country not in normalized:
            normalized.append(country)
    if not normalized:
        return "UNKNOWN"
    return " | ".join(normalized)


def infer_country(text: str) -> str:
    lowered = normalize_space(text).casefold()
    matches = []
    for country, needles in COUNTRY_PATTERNS:
        if any(needle in lowered for needle in needles):
            matches.append(country)
    if not matches:
        return "UNKNOWN"
    deduped = []
    for country in matches:
        if country not in deduped:
            deduped.append(country)
    return normalize_country_value(" | ".join(deduped))


def clean_affiliation(text: str) -> str:
    replacements = {
        "Amazon.com": "Amazon",
        "SnapDeal.com": "SnapDeal",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)

    text = re.sub(r"[\u2020\u2021\u00a7†‡§]", " ", text)
    text = re.sub(r"\[[^\]]*\]\s*@\s*\S*", " ", text)
    text = re.sub(r"\{[^}]*\}\s*@\s*\S*", " ", text)
    text = re.sub(r"\b[\w.\-+]+(?:\s*,\s*[\w.\-+]+){0,12}\s*@\s*[\w.\-+]*", " ", text)
    text = re.sub(r"\b\S+\s+@\S+\b", " ", text)
    text = re.sub(r"\b[\w.\-+]+(?:\s*,\s*[\w.\-+]+)*\s*@\s*[\w.\-]+\b", " ", text)
    text = re.sub(r"\S+@\S+", " ", text)
    text = re.sub(r"[A-Za-z0-9_.+\-]+(?:\s*,\s*[A-Za-z0-9_.+\-]+){0,20}\s*@\s*$", " ", text)
    text = re.sub(r"https?://\S+", " ", text)
    text = re.sub(r"\b[\w.-]+\.(?:edu|com|org|net|fr|au|tw|kr|co|ac\.kr|edu\.tw|edu\.au)\b", " ", text)
    text = re.sub(r"\b([A-Za-z][A-Za-z0-9&+\-]*)\.com\b", r"\1", text)
    text = re.sub(r"\b\d+\b", " ", text)
    text = text.replace("{", " ").replace("}", " ")
    text = re.sub(r"\s*\|\s*", " | ", text)
    text = re.sub(r"\s*,\s*,+", ", ", text)
    for stopper in [
        " As rank minimization",
        " As a simple example",
        " Abstract",
        " ",
        " ]",
    ]:
        if stopper in text:
            text = text.split(stopper, 1)[0]
    text = normalize_space(text.strip(" ,;"))
    if not text:
        return "UNKNOWN"
    return text


def read_preamble(path: Path) -> str:
    text = path.read_text(encoding="utf-8", errors="replace")
    return text.split("Abstract", 1)[0]


def preamble_lines(preamble: str):
    return [line.strip() for line in preamble.splitlines() if line.strip()]


def split_inline_numbered_segments(text: str):
    return [
        part.strip(" ,;")
        for part in re.split(r"\s(?=\d+\s+)", normalize_space(text))
        if part.strip(" ,;")
    ]


def split_numbered_affiliations(preamble: str, author_names):
    lines = preamble_lines(preamble)
    mapping = {}
    pending_labels = []

    for line in lines:
        if "@" in line or line.lower().startswith("abstract"):
            break
        if any(name in line for name in author_names):
            continue
        if re.fullmatch(r"(?:\d+\s*)+", line):
            pending_labels.extend(re.findall(r"\d+", line))
            continue

        segments = split_inline_numbered_segments(line)
        if not segments:
            continue

        first = segments[0]
        if pending_labels and not re.match(r"^\d+\s+", first):
            label = pending_labels.pop(0)
            mapping.setdefault(label, first)
            segments = segments[1:]

        for segment in segments:
            match = re.match(r"^(\d+)\s+(.+)$", segment)
            if match:
                mapping.setdefault(match.group(1), match.group(2).strip(" ,;"))

    return {label: value for label, value in mapping.items() if len(value) >= 3}


def author_label_map(preamble: str, author_names):
    compact = normalize_space(preamble)
    mapping = {}
    for name in author_names:
        match = re.search(re.escape(name) + r"\s*([0-9,]+)", compact)
        if match:
            mapping[name] = [label for label in match.group(1).split(",") if label]
    return mapping


def split_symbol_affiliations(preamble: str):
    lines = preamble_lines(preamble)
    mapping = {}
    for i, line in enumerate(lines):
        match = re.match(r"^[†‡§*∗]\s*(.+)$", line)
        if not match:
            continue
        block = [match.group(1).strip()]
        j = i + 1
        while j < len(lines):
            nxt = lines[j]
            if re.match(r"^[†‡§*∗]\s*", nxt):
                break
            if "@" in nxt or nxt.lower().startswith("abstract"):
                break
            if any(ch.isdigit() for ch in nxt[:2]) and len(nxt.split()) < 6:
                break
            block.append(nxt)
            j += 1
        mapping[line[0]] = clean_affiliation(" ".join(block))
    return mapping


def author_symbol_map(preamble: str, author_names):
    compact = normalize_space(preamble)
    mapping = {}
    for name in author_names:
        match = re.search(re.escape(name) + r"\s*([†‡§*∗]+)", compact)
        if match:
            mapping[name] = list(match.group(1))
    return mapping


def parse_numbered_variant(preamble: str, author_names):
    numbered_affiliations = split_numbered_affiliations(preamble, author_names)
    labels_by_author = author_label_map(preamble, author_names)
    assigned = {}
    if numbered_affiliations and labels_by_author:
        for author_name, labels in labels_by_author.items():
            affiliation = " | ".join(
                numbered_affiliations[label]
                for label in labels
                if label in numbered_affiliations
            ).strip(" |")
            if affiliation:
                assigned[author_name] = clean_affiliation(affiliation)
    return assigned


def parse_symbol_variant(preamble: str, author_names):
    symbol_affiliations = split_symbol_affiliations(preamble)
    symbols_by_author = author_symbol_map(preamble, author_names)
    assigned = {}
    if symbol_affiliations and symbols_by_author:
        for author_name, symbols in symbols_by_author.items():
            affiliation = " | ".join(
                symbol_affiliations[symbol]
                for symbol in symbols
                if symbol in symbol_affiliations
            ).strip(" |")
            if affiliation:
                assigned[author_name] = clean_affiliation(affiliation)
    return assigned


def parse_stacked_variant(preamble: str, author_names):
    lines = preamble_lines(preamble)
    assigned = {}
    current_authors = []
    current_block = []

    def flush():
        nonlocal current_authors, current_block
        if current_authors and current_block:
            affiliation = clean_affiliation(" ".join(current_block))
            if affiliation != "UNKNOWN":
                for author_name in current_authors:
                    assigned[author_name] = affiliation
        current_authors = []
        current_block = []

    for line in lines:
        lowered = line.lower()
        if "@" in line or lowered.startswith("abstract"):
            break
        names_in_line = [name for name in author_names if name in line]
        if names_in_line and not re.search(
            r"\b(university|institute|college|inc\.?|corp\.?|research|laboratory|lab|academy|school|department|dept\.?)\b",
            lowered,
        ):
            flush()
            current_authors = names_in_line
            continue
        if current_authors:
            current_block.append(line)

    flush()
    if len(assigned) < 2:
        return {}
    return assigned


def parse_shared_variant(preamble: str, author_names):
    lines = preamble_lines(preamble)
    if not author_names:
        return {}

    affiliation_lines = []
    for line in lines:
        lowered = line.lower()
        if "@" in line or lowered.startswith("abstract"):
            break
        if any(name in line for name in author_names):
            continue
        if re.fullmatch(r"(?:\d+\s*)+", line):
            continue
        if re.search(
            r"\b(university|institute|college|academy|research|laboratory|lab|center|centre|school|department|dept\.?|inc\.?|corp\.?|microsoft|google|qualcomm|kaist|kist)\b",
            lowered,
        ):
            affiliation_lines.append(line)

    if len(affiliation_lines) == 1:
        affiliation = clean_affiliation(affiliation_lines[0])
        if affiliation != "UNKNOWN":
            return {name: affiliation for name in author_names}

    author_positions = []
    for name in author_names:
        try:
            author_positions.append(next(i for i, line in enumerate(lines) if name in line))
        except StopIteration:
            return {}

    end = max(author_positions)
    block = []
    for line in lines[end + 1 :]:
        if "@" in line or line.lower().startswith("abstract"):
            break
        if re.match(r"^[†‡§*∗]\s*", line):
            continue
        if line in author_names:
            break
        block.append(line)

    affiliation = clean_affiliation(" ".join(block))
    if affiliation == "UNKNOWN":
        return {}
    return {name: affiliation for name in author_names}


def detect_variants(preamble: str):
    compact = normalize_space(preamble)
    variants = []
    if re.search(r"\b\d\b\s+[A-Z]", compact):
        variants.append("numbered")
    if re.search(r"[†‡§*∗]", compact):
        variants.append("symbol")
    if "@" in preamble and "\n\n" in preamble:
        variants.append("stacked")
    variants.append("shared")
    return variants


def affiliation_quality(text: str, author_name: str, all_author_names):
    if not text or text == "UNKNOWN":
        return -1000

    lowered = text.casefold()
    score = 0
    keywords = [
        "university",
        "institute",
        "college",
        "school",
        "department",
        "dept",
        "academy",
        "research",
        "laboratory",
        "lab",
        "center",
        "centre",
        "corporation",
        "corp",
        "inc",
        "google",
        "microsoft",
        "qualcomm",
        "kaist",
        "cmu",
        "academia sinica",
    ]
    score += sum(2 for keyword in keywords if keyword in lowered)
    score += 2 * (infer_country(text) != "UNKNOWN")
    score += min(text.count("|"), 2)

    if re.search(r"\b(proceedings|notice of violation|publication principles|figure \d|copyright|source|ours)\b", lowered):
        score -= 12
    if lowered.startswith("/") or "projects/" in lowered:
        score -= 10
    if len(text.split()) > 30:
        score -= 6
    if not re.search(r"[A-Za-z]{3}", text):
        score -= 8

    author_hits = 0
    for other_name in all_author_names:
        if other_name == author_name:
            continue
        surname = other_name.split()[-1].casefold()
        if len(surname) >= 4 and surname in lowered:
            author_hits += 1
    score -= author_hits * 4

    org_hits = len(
        re.findall(
            r"\b(university|institute|college|academy|research|inc\.?|corp\.?|laboratory|lab|school|department)\b",
            lowered,
        )
    )
    if "|" not in text and org_hits >= 3:
        score -= 5

    return score


def build_authors_for_paper(paper_authors):
    authors_for_paper = defaultdict(list)
    for row in paper_authors:
        authors_for_paper[row["paper_id"]].append(row)
    for rows in authors_for_paper.values():
        rows.sort(key=lambda row: int(row["author_position"]))
    return dict(authors_for_paper)


def extract_candidate_rows(authors, paper_authors, papers_index_rows, first_pages_dir: Path):
    authors_by_id = {row["author_id"]: row for row in authors}
    authors_for_paper = build_authors_for_paper(paper_authors)
    papers_index = {row["paper_id"]: row for row in papers_index_rows}
    rows = []

    for paper_id, paper_row in papers_index.items():
        txt_path = first_pages_dir / f"{paper_id}.txt"
        if not txt_path.exists():
            continue

        ordered_rows = authors_for_paper.get(paper_id, [])
        ordered_author_ids = [row["author_id"] for row in ordered_rows]
        ordered_author_names = [authors_by_id[author_id]["author_name"] for author_id in ordered_author_ids]
        if not ordered_author_names:
            continue

        preamble = read_preamble(txt_path)
        variants = detect_variants(preamble)
        if any(variant in variants for variant in ["numbered", "symbol"]):
            variants = [variant for variant in variants if variant != "shared"] + ["shared"]

        variant_candidates = {}
        for variant in variants:
            if variant == "numbered":
                variant_candidates[variant] = parse_numbered_variant(preamble, ordered_author_names)
            elif variant == "symbol":
                variant_candidates[variant] = parse_symbol_variant(preamble, ordered_author_names)
            elif variant == "stacked":
                variant_candidates[variant] = parse_stacked_variant(preamble, ordered_author_names)
            else:
                variant_candidates[variant] = parse_shared_variant(preamble, ordered_author_names)

        for variant in variants:
            candidate_map = variant_candidates.get(variant, {})
            coverage = sum(1 for name in ordered_author_names if candidate_map.get(name))
            for author_id, author_name in zip(ordered_author_ids, ordered_author_names):
                block = clean_affiliation(candidate_map.get(author_name, "UNKNOWN"))
                score = affiliation_quality(block, author_name, ordered_author_names)
                rows.append(
                    {
                        "paper_id": paper_id,
                        "author_id": author_id,
                        "author_name": author_name,
                        "variant": variant,
                        "variant_priority": str(VARIANT_PRIORITY.get(variant, 99)),
                        "variant_coverage": str(coverage),
                        "author_count": str(len(ordered_author_names)),
                        "institution_candidate": block,
                        "candidate_score": str(score),
                        "first_page_text_path": str(txt_path),
                        "source_url": paper_row["pdf_url"],
                    }
                )

    return rows


def select_affiliation_links(candidate_rows, min_score=MIN_AFFILIATION_SCORE):
    rows_by_paper = defaultdict(list)
    for row in candidate_rows:
        rows_by_paper[row["paper_id"]].append(row)

    selected = []

    for paper_id, paper_rows in rows_by_paper.items():
        rows_by_variant = defaultdict(list)
        rows_by_author = defaultdict(list)
        for row in paper_rows:
            rows_by_variant[row["variant"]].append(row)
            rows_by_author[row["author_id"]].append(row)

        complete_variants = []
        for variant, variant_rows in rows_by_variant.items():
            author_count = int(variant_rows[0]["author_count"])
            viable = [row for row in variant_rows if int(row["candidate_score"]) >= min_score and row["institution_candidate"] != "UNKNOWN"]
            if len(viable) == author_count:
                complete_variants.append(
                    (
                        VARIANT_PRIORITY.get(variant, 99),
                        -sum(int(row["candidate_score"]) for row in viable),
                        variant,
                        viable,
                    )
                )

        if complete_variants:
            complete_variants.sort()
            _, _, chosen_variant, chosen_rows = complete_variants[0]
            for row in sorted(chosen_rows, key=lambda candidate: candidate["author_id"]):
                selected.append(
                    {
                        "paper_id": paper_id,
                        "author_id": row["author_id"],
                        "author_name": row["author_name"],
                        "selected_variant": chosen_variant,
                        "selection_reason": f"complete_{chosen_variant}_variant",
                        "institution_raw": row["institution_candidate"],
                        "candidate_score": row["candidate_score"],
                        "first_page_text_path": row["first_page_text_path"],
                        "source_url": row["source_url"],
                    }
                )
            continue

        for author_id, author_rows in rows_by_author.items():
            viable = [
                row
                for row in author_rows
                if int(row["candidate_score"]) >= min_score and row["institution_candidate"] != "UNKNOWN"
            ]
            if viable:
                viable.sort(
                    key=lambda row: (
                        -int(row["candidate_score"]),
                        VARIANT_PRIORITY.get(row["variant"], 99),
                        -int(row["variant_coverage"]),
                    )
                )
                best = viable[0]
                selected.append(
                    {
                        "paper_id": paper_id,
                        "author_id": author_id,
                        "author_name": best["author_name"],
                        "selected_variant": best["variant"],
                        "selection_reason": "best_scoring_candidate",
                        "institution_raw": best["institution_candidate"],
                        "candidate_score": best["candidate_score"],
                        "first_page_text_path": best["first_page_text_path"],
                        "source_url": best["source_url"],
                    }
                )
            else:
                fallback = sorted(
                    author_rows,
                    key=lambda row: (
                        VARIANT_PRIORITY.get(row["variant"], 99),
                        -int(row["variant_coverage"]),
                    ),
                )[0]
                selected.append(
                    {
                        "paper_id": paper_id,
                        "author_id": author_id,
                        "author_name": fallback["author_name"],
                        "selected_variant": fallback["variant"],
                        "selection_reason": "no_viable_candidate",
                        "institution_raw": "UNKNOWN",
                        "candidate_score": fallback["candidate_score"],
                        "first_page_text_path": fallback["first_page_text_path"],
                        "source_url": fallback["source_url"],
                    }
                )

    selected.sort(key=lambda row: (row["paper_id"], row["author_id"]))
    return selected


def reset_parse_sourced_authors(authors):
    for author in authors:
        if author.get("source_note") == PARSE_SOURCE_NOTE:
            author["institution"] = "UNKNOWN"
            author["country"] = "UNKNOWN"
            author["source_url"] = ""
            author["source_note"] = ""
    return authors


def apply_selected_institutions(authors, link_rows):
    authors_by_id = {row["author_id"]: row for row in authors}
    reset_parse_sourced_authors(authors)

    for row in link_rows:
        cleaned = clean_affiliation(row["institution_raw"])
        if cleaned == "UNKNOWN":
            continue
        author = authors_by_id[row["author_id"]]
        author["institution"] = cleaned
        author["source_url"] = row["source_url"]
        author["source_note"] = PARSE_SOURCE_NOTE
        author["country"] = "UNKNOWN"

    return authors


def build_institution_rows(link_rows):
    rows = []
    for row in link_rows:
        rows.append(
            {
                "paper_id": row["paper_id"],
                "author_id": row["author_id"],
                "author_name": row["author_name"],
                "selected_variant": row["selected_variant"],
                "selection_reason": row["selection_reason"],
                "institution_raw": row["institution_raw"],
                "institution_normalized": clean_affiliation(row["institution_raw"]),
                "candidate_score": row["candidate_score"],
                "first_page_text_path": row["first_page_text_path"],
                "source_url": row["source_url"],
            }
        )
    return rows


def apply_inferred_countries(authors):
    for author in authors:
        if author["institution"] == "UNKNOWN":
            author["country"] = "UNKNOWN"
        else:
            author["country"] = infer_country(author["institution"])
    return authors


def build_country_rows(authors):
    return [
        {
            "author_id": row["author_id"],
            "author_name": row["author_name"],
            "institution": row["institution"],
            "country": row["country"],
            "conference": row["conference"],
            "year": row["year"],
        }
        for row in authors
    ]
