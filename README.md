# ConferenceStats

This repository is organized around a three-step workflow for building conference-level country contribution statistics over time.

The goal is to collect structured metadata for every conference and year, normalize it into a consistent CSV format, and then compute overview statistics such as the percentage of papers with at least one author from a specific country.

## Context

This repository is motivated in part by the Medium article [A decade of change: China’s rise in AI research and the global talent flow](https://medium.com/data-science-collective/a-decade-of-change-chinas-rise-in-ai-research-and-the-global-talent-flow-d9c49ebd4d37).

That post used estimated conference shares from a visual summary rather than a full paper-by-paper metadata collection pipeline. The goal here is to replace those estimates with reproducible conference/year datasets and downstream statistics.

For context, this repository treats `ICCV` and `ECCV` as one conference family for analysis, even though the source data is stored under the actual venue name for each year:

- odd years: `ICCV`
- even years: `ECCV`

## Workflow Overview

### Step 1: Collect conference/year data

Use [get_conference_stats.md](/Users/maier/Documents/code/ConferenceStats/get_conference_stats.md) as the collection workflow.

This step is intended to be performed by agents in parallel, one conference/year at a time. Each agent should:

- Find the official proceedings or table of contents for a conference/year.
- Expand multi-volume proceedings into the full main-conference corpus when applicable.
- Use scripts to retrieve and structure raw data before any LLM-based enrichment.
- Extract paper titles, author names, and author order.
- Derive institution and country information in explicit passes rather than one monolithic enrichment step.
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

To run the optional local-LLM country pass yourself for one dataset:

```bash
make llm-country CONFERENCE_SLUG=cvpr YEAR=2016
```

To fetch CVPR proceedings metadata plus PDF first pages for one year:

```bash
make cvpr-first-pages YEAR=2018
```

To fetch them for the full `2018` through `2025` range:

```bash
make cvpr-first-pages-range CVPR_START_YEAR=2018 CVPR_END_YEAR=2025
```

To test just the first 100 papers for each `CVPR` year from `2018` through `2025`:

```bash
make cvpr-first-pages-range-sample
```

This uses zero-based indexing internally, so `FIRST_PAGE_START=0` and `FIRST_PAGE_LIMIT=100` means papers `1` through `100`.

To check the per-year first-page extraction status afterward:

```bash
make cvpr-first-pages-status-range CVPR_START_YEAR=2021 CVPR_END_YEAR=2025
```

After first-page extraction finishes for a year, prepare the deterministic intermediate files that the local-LLM pass will build on:

```bash
make cvpr-prepare-llm YEAR=2018
```

Then run the local-LLM country fill manually:

```bash
make llm-country CONFERENCE_SLUG=cvpr YEAR=2018
```

For the `ICCV/ECCV` family, the year resolves automatically to the right source venue:

```bash
make iccv-eccv-show-target YEAR=2024
make iccv-eccv-first-pages YEAR=2016 FIRST_PAGE_START=0 FIRST_PAGE_LIMIT=100
make iccv-eccv-first-pages-sample-2015-2016
make iccv-eccv-first-pages-sample-remaining
make iccv-eccv-prepare-llm YEAR=2024
make iccv-eccv-llm-country YEAR=2024
```

For ECCV years, the family target now auto-discovers linked Springer proceedings volumes from the Part I page and excludes workshop volumes. If we ever need to override or pin a year manually, we can still add a manifest under `config/proceedings_volumes/eccv/<year>.csv`.

To probe a custom year range for the first 100 papers, use:

```bash
make iccv-eccv-first-pages-range ICCV_ECCV_START_YEAR=2017 ICCV_ECCV_END_YEAR=2025 FIRST_PAGE_START=0 FIRST_PAGE_LIMIT=100
```

## Repository Layout

```text
config/
  conferences.csv          # list of conference/year collection targets
  proceedings_volumes/     # optional per-year multi-volume proceedings manifests
data/
  raw/                     # raw downloaded or copied source material
  normalized/              # canonical CSV outputs per conference/year
  intermediate/            # step-1 intermediate artifacts per enrichment pass
output/                    # generated statistics and overview tables
scripts/
  affiliation_pipeline.py
  compute_country_stats.py
  build_overview_table.py
  collect_cvf_openaccess.py
  extract_affiliation_candidates.py
  extract_pdf_first_pages.py
  enrich_from_first_pages.py
  fill_unknown_countries_with_local_llm.py
  link_author_affiliations.py
  local_llm.py
  normalize_institutions.py
  infer_countries.py
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

For CVF Open Access conferences, the script-first path is:

```bash
python3 scripts/collect_cvf_openaccess.py \
  --conference CVPR \
  --conference-slug cvpr \
  --year 2015 \
  --proceedings-url https://openaccess.thecvf.com/CVPR2015 \
  --raw-dir data/raw/cvpr/2015 \
  --normalized-dir data/normalized/cvpr/2015
```

Then retrieve raw first-page text for later affiliation/country enrichment:

```bash
python3 scripts/extract_pdf_first_pages.py \
  --papers-index data/raw/cvpr/2015/papers_index.csv \
  --output-dir data/raw/cvpr/2015/first_pages \
  --manifest data/raw/cvpr/2015/first_page_manifest.csv \
  --start 0 \
  --limit 100 \
  --workers 4
```

The equivalent `make` shortcuts for CVPR are:

```bash
make cvpr-first-pages YEAR=2018
make cvpr-first-pages-range CVPR_START_YEAR=2018 CVPR_END_YEAR=2025
```

The first-page extractor supports bounded parallelism. The `make` targets expose it as `FIRST_PAGE_WORKERS`, which defaults to `4`.

```bash
make cvpr-first-pages YEAR=2018 FIRST_PAGE_WORKERS=6
make iccv-eccv-first-pages YEAR=2022 FIRST_PAGE_WORKERS=6 FIRST_PAGE_START=0 FIRST_PAGE_LIMIT=100
```

Then run the enrichment passes. The recommended one-command wrapper is:

```bash
python3 scripts/enrich_from_first_pages.py \
  --authors-csv data/normalized/cvpr/2015/authors.csv \
  --paper-authors-csv data/normalized/cvpr/2015/paper_authors.csv \
  --papers-index data/raw/cvpr/2015/papers_index.csv \
  --first-pages-dir data/raw/cvpr/2015/first_pages \
  --output-authors-csv data/normalized/cvpr/2015/authors.csv \
  --intermediate-dir data/intermediate/cvpr/2015
```

That wrapper now performs four explicit passes:

1. `extract_affiliation_candidates.py`
Creates `data/intermediate/<conference_slug>/<year>/affiliation_candidates.csv` with all variant-based author-affiliation candidates from the first pages.

2. `link_author_affiliations.py`
Chooses one affiliation candidate per author and writes `author_affiliations.csv`.

3. `normalize_institutions.py`
Normalizes the chosen affiliations and writes `author_institutions.csv` plus an updated `authors.csv` with populated `institution`.

4. `infer_countries.py`
Derives `country` from normalized `institution` and writes `author_countries.csv` plus the final updated `authors.csv`.

You can also run those passes separately when debugging:

```bash
python3 scripts/extract_affiliation_candidates.py \
  --authors-csv data/normalized/cvpr/2015/authors.csv \
  --paper-authors-csv data/normalized/cvpr/2015/paper_authors.csv \
  --papers-index data/raw/cvpr/2015/papers_index.csv \
  --first-pages-dir data/raw/cvpr/2015/first_pages \
  --output-candidates-csv data/intermediate/cvpr/2015/affiliation_candidates.csv

python3 scripts/link_author_affiliations.py \
  --candidates-csv data/intermediate/cvpr/2015/affiliation_candidates.csv \
  --output-links-csv data/intermediate/cvpr/2015/author_affiliations.csv

python3 scripts/normalize_institutions.py \
  --authors-csv data/normalized/cvpr/2015/authors.csv \
  --links-csv data/intermediate/cvpr/2015/author_affiliations.csv \
  --output-authors-csv data/normalized/cvpr/2015/authors.csv \
  --output-institutions-csv data/intermediate/cvpr/2015/author_institutions.csv

python3 scripts/infer_countries.py \
  --authors-csv data/normalized/cvpr/2015/authors.csv \
  --output-authors-csv data/normalized/cvpr/2015/authors.csv \
  --output-countries-csv data/intermediate/cvpr/2015/author_countries.csv \
  --use-local-llm \
  --llm-review-csv data/intermediate/cvpr/2015/author_country_llm_review.csv
```

For large conferences, step 1 should be run as a loop:

1. Develop or fix the conference-family retrieval/parsing script.
2. Run raw-data extraction in chunks.
3. Rerun the four enrichment passes after each chunk.
4. Validate the normalized outputs.
5. Repeat until the conference/year dataset is complete or reaches acceptable coverage.

## Optional Local LLM Pass

For author rows where `institution` is known but `country` remains `UNKNOWN`, the repository can use a local Ollama model as a conservative follow-up pass.

Project-level config lives in [local_llm.json](/Users/maier/Documents/code/ConferenceStats/config/local_llm.json). The default setup uses:

- provider: `ollama`
- base URL: `http://localhost:11434`
- model: `qwen3:14b`

Use the shared client in [local_llm.py](/Users/maier/Documents/code/ConferenceStats/scripts/local_llm.py) so all scripts talk to the same local model configuration.

The recommended project-wide setup is:

```bash
open -a Ollama
ollama pull qwen3:14b
ollama list
```

Once that is in place, any script can opt into the shared local model by reading `config/local_llm.json` through `scripts/local_llm.py`.

The recommended console entry point is:

```bash
make llm-country CONFERENCE_SLUG=cvpr YEAR=2016
```

That runs the shared `infer_countries.py --use-local-llm` flow and writes:

- `data/normalized/<conference_slug>/<year>/authors.csv`
- `data/intermediate/<conference_slug>/<year>/author_countries.csv`
- `data/intermediate/<conference_slug>/<year>/author_country_llm_review.csv`

To fill `UNKNOWN` countries from institution strings:

```bash
python3 scripts/infer_countries.py \
  --authors-csv data/normalized/cvpr/2015/authors.csv \
  --output-authors-csv data/normalized/cvpr/2015/authors.csv \
  --output-countries-csv data/intermediate/cvpr/2015/author_countries.csv \
  --use-local-llm \
  --llm-review-csv data/intermediate/cvpr/2015/author_country_llm_review.csv \
  --llm-min-confidence medium
```

This step should remain optional and conservative:

- only run it after institution normalization
- only target rows with known `institution` and `UNKNOWN` `country`
- keep a review CSV with the model's proposed country, confidence, and explanation
- avoid overwriting good country assignments from deterministic rules

## Notes on Author IDs

This scaffold treats `author_id` as a stable dataset-local identifier, not as a globally disambiguated person identifier across all years and conferences.

That keeps collection practical and reproducible. If you later want person-level identity resolution across years, that should be added as a separate enrichment step rather than mixed into the initial collection workflow.
