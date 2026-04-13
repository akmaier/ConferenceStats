# Step 1 Workflow: Gather Conference Proceedings Data

This workflow is designed for agent-based parallel collection.

Each agent owns one `conference_slug + year` pair and produces raw source material plus normalized CSVs that conform to this repository's data contract.

## Goal

For each conference/year:

- find the official proceedings, table of contents, or publisher landing page
- expand multi-volume proceedings into the full main-conference volume set when applicable
- extract accepted paper titles
- extract author names and author order
- identify institutions of the authors when available
- infer or collect author countries from institution information
- save normalized CSV outputs for later statistics

## Inputs

Read targets from:

- [config/conferences.csv](/Users/maier/Documents/code/ConferenceStats/config/conferences.csv)

Each row should define:

- `conference`
- `conference_slug`
- `year`
- `proceedings_url`
- `publisher`
- `status`
- `notes`

## Parallelization Strategy

Run one agent per conference/year row where `status` is not `done`.

Recommended unit of work:

- conference/year pairs are independent
- agents should not edit the same target folder
- each agent writes only under:
  - `data/raw/<conference_slug>/<year>/`
  - `data/normalized/<conference_slug>/<year>/`

## Required Output Structure

For conference slug `neurips` and year `2025`, the agent should create:

```text
data/raw/neurips/2025/
  collection_notes.md
  source_manifest.csv
  proceedings_volumes.csv          # required when proceedings span multiple volumes
  proceedings_landing_page.html       # optional if downloaded
  toc.html                            # optional if downloaded
  toc.pdf                             # optional if proceedings are PDF-based

data/normalized/neurips/2025/
  authors.csv
  papers.csv
  paper_authors.csv
```

## CSV Requirements

### `authors.csv`

One row per author record used in this conference/year dataset.

Required columns:

- `author_id`
- `author_name`
- `country`
- `institution`
- `conference`
- `year`
- `source_url`
- `source_note`

Rules:

- Use deterministic IDs such as `NEURIPS-2025-A0001`.
- If multiple institutions are listed, join them with ` | `.
- If country cannot be verified, use `UNKNOWN`.
- If institution cannot be verified, use `UNKNOWN`.
- `source_note` should briefly explain where the institution/country came from.

### `papers.csv`

One row per accepted paper in the proceedings.

Required columns:

- `paper_id`
- `title`
- `author_ids`
- `conference`
- `year`
- `source_url`

Rules:

- Use deterministic IDs such as `NEURIPS-2025-P0001`.
- `author_ids` must be a pipe-separated list matching `authors.csv`.
- Include only accepted papers that belong to the main proceedings corpus for the chosen conference/year unless the target row explicitly says otherwise.

### `paper_authors.csv`

Canonical mapping table for analysis.

Required columns:

- `paper_id`
- `author_id`
- `author_position`

Rules:

- One row per paper-author pair.
- `author_position` starts at `1`.

## Collection Procedure

For each assigned conference/year:

1. Open the proceedings URL or find the official proceedings page if the config row only has a landing page.
2. If the proceedings are split across several books or parts, enumerate the full main-conference volume set first and record it in `proceedings_volumes.csv`.
3. Identify the main accepted-paper list or table of contents across the full proceedings corpus.
4. Extract all paper titles and ordered author lists.
5. For each author, collect institution and country information from the proceedings page, paper page, PDF first page, supplemental metadata, or publisher metadata.
6. Save provenance in `data/raw/<conference_slug>/<year>/collection_notes.md`.
7. Write normalized CSVs into `data/normalized/<conference_slug>/<year>/`.
8. Ensure IDs and references are internally consistent.

## Provenance Rules

Every agent should create `collection_notes.md` containing:

- conference name and year
- proceedings URL used
- scope decisions
- any exclusions
- any ambiguous institution or country assignments
- unresolved missing metadata

For multi-volume conferences, `collection_notes.md` should also say which volumes were included in the main conference corpus and which were excluded.

Every agent should also create `source_manifest.csv` with:

- `source_url`
- `source_type`
- `used_for`
- `notes`

When proceedings span several books or parts, also create `proceedings_volumes.csv` with:

- `volume_label`
- `volume_url`
- `included`
- `notes`

## Quality Rules

- Prefer official publisher or conference proceedings sources.
- For multi-volume conferences, collect all main-conference volumes before starting normalization.
- Preserve author order exactly.
- Do not guess countries from author names.
- Infer country from institution only when the institution is clear.
- Keep `UNKNOWN` rather than making a weak guess.
- Record ambiguous cases in `collection_notes.md`.

## Validation

After agents finish, run:

```bash
make validate
```

This checks that:

- required files exist
- required CSV columns are present
- `paper_id` and `author_id` references are consistent
- IDs are unique within each dataset

## Handoff to Step 2

Once normalized datasets exist, compute country statistics with:

```bash
make stats COUNTRY=China
```

Then generate the conference-by-year overview table with:

```bash
make overview COUNTRY=China
```
