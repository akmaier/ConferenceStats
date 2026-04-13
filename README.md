# ConferenceStats

This repository is organized around a three-step workflow for building conference-level country contribution statistics over time.

The goal is to collect structured metadata for every conference and year, normalize it into a consistent CSV format, and then compute overview statistics such as the percentage of papers with at least one author from a specific country.

## Workflow Overview

### Step 1: Collect conference/year data

Use [get_conference_stats.md](/Users/maier/Documents/code/ConferenceStats/get_conference_stats.md) as the collection workflow.

This step is intended to be performed by agents in parallel, one conference/year at a time. Each agent should:

- Find the official proceedings or table of contents for a conference/year.
- Expand multi-volume proceedings into the full main-conference corpus when applicable.
- Extract paper titles, author names, and author order.
- Record institution and country information for each author when available.
- Save both raw source artifacts and normalized CSV outputs.
- Keep provenance notes so later analysis can be audited.

### Step 2: Compute country statistics

This step reads normalized CSVs and computes, for each conference/year:

- total accepted papers
- number of papers with at least one author from a target country
- percentage share of papers with that country's participation

Run:

```bash
make stats COUNTRY=China
```

Outputs:

- `output/country_stats.csv`
- `output/country_stats.md`

### Step 3: Build overview table

This step pivots the step-2 statistics into an overview table by conference and year.

Run:

```bash
make overview COUNTRY=China
```

Outputs:

- `output/country_overview.csv`
- `output/country_overview.md`

To run both steps together:

```bash
make all COUNTRY=China
```

## Repository Layout

```text
config/
  conferences.csv          # list of conference/year collection targets
data/
  raw/                     # raw downloaded or copied source material
  normalized/              # canonical CSV outputs per conference/year
  intermediate/            # optional temporary merged datasets
output/                    # generated statistics and overview tables
scripts/
  compute_country_stats.py
  build_overview_table.py
  validate_collection.py
get_conference_stats.md    # markdown workflow for agent-driven collection
Makefile                   # entry points for steps 2 and 3
```

## Data Contract

For each conference/year, create:

`data/normalized/<conference_slug>/<year>/authors.csv`

Required columns:

- `author_id`
- `author_name`
- `country`
- `institution`
- `conference`
- `year`
- `source_url`
- `source_note`

`data/normalized/<conference_slug>/<year>/papers.csv`

Required columns:

- `paper_id`
- `title`
- `author_ids`
- `conference`
- `year`
- `source_url`

`data/normalized/<conference_slug>/<year>/paper_authors.csv`

Required columns:

- `paper_id`
- `author_id`
- `author_position`

The `author_ids` column in `papers.csv` should be a pipe-separated list such as `CONF-2025-A0001|CONF-2025-A0002`.

`paper_authors.csv` is the canonical relational mapping used by the scripts. The list inside `papers.csv` is kept as a convenience export for downstream tooling.

For conferences split across several proceedings books, agents should also create `data/raw/<conference_slug>/<year>/proceedings_volumes.csv` with columns such as `volume_label`, `volume_url`, `included`, and `notes`.

## Collection Targets

Fill `config/conferences.csv` with one row per conference/year target. Suggested columns:

- `conference`
- `conference_slug`
- `year`
- `proceedings_url`
- `publisher`
- `status`
- `notes`

For multi-volume proceedings such as `MICCAI` and some `ECCV` editions, `proceedings_url` may point to a representative entry page such as Part I. Collection must still cover all main-conference proceedings volumes for that year, not only the linked volume.

Example workflow:

1. Add all desired conference/year rows to `config/conferences.csv`.
2. Run the step-1 workflow in [get_conference_stats.md](/Users/maier/Documents/code/ConferenceStats/get_conference_stats.md).
3. Validate the resulting normalized datasets with:

```bash
make validate
```

4. Compute country-specific statistics and overview tables with `make`.

## Notes on Author IDs

This scaffold treats `author_id` as a stable dataset-local identifier, not as a globally disambiguated person identifier across all years and conferences.

That keeps collection practical and reproducible. If you later want person-level identity resolution across years, that should be added as a separate enrichment step rather than mixed into the initial collection workflow.
