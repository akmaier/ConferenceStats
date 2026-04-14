# Step 1 Workflow: Gather Conference Proceedings Data

This workflow is designed for agent-based parallel collection.

Each agent owns one `conference_slug + year` pair and produces raw source material plus normalized CSVs that conform to this repository's data contract.

The default preference is script-first collection: use scripts to fetch and structure raw data, and reserve LLM reasoning for extracting or normalizing information from already downloaded raw artifacts.

Think of step 1 as two substeps:

## Step 1a: Develop and bug-fix the script

Goal:

- identify the proceedings structure for the conference family
- write or adapt a deterministic retrieval/parsing script
- test it on one conference/year until the normalized CSVs are structurally correct

Deliverables:

- raw proceedings page or equivalent source artifact on disk
- normalized CSV parse for titles, author order, and paper links
- any script fixes needed for that conference family

## Step 1b: Loop over chunks to iteratively fill the dataset

Goal:

- use the script from step 1a to retrieve raw data in manageable chunks
- extract first-page text or other raw metadata files incrementally
- rerun the explicit affiliation pipeline after each chunk
- keep the normalized CSVs updated as raw coverage improves

## Goal

For each conference/year:

- find the official proceedings, table of contents, or publisher landing page
- expand multi-volume proceedings into the full main-conference volume set when applicable
- use scripts for retrieval and parsing whenever a conference family has a stable structure
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

data/intermediate/neurips/2025/
  affiliation_candidates.csv       # raw author-affiliation candidates per parser variant
  author_affiliations.csv          # chosen affiliation link per author
  author_institutions.csv          # normalized institution rows
  author_countries.csv             # countries inferred from normalized institutions
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
- Populate `institution` only after the institution-normalization pass.
- If country cannot be verified, use `UNKNOWN`.
- Populate `country` only after the country-inference pass.
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
3. Prefer a deterministic script to retrieve the proceedings page and parse the paper list.
4. Extract all paper titles and ordered author lists into normalized CSVs, even if institution enrichment is still pending.
5. Retrieve paper PDFs or first-page text as raw artifacts when affiliations or countries are not present on the proceedings page.
6. Run the enrichment pipeline in passes:
7. First extract raw author-affiliation candidates from the downloaded first-page text.
8. Then link authors to the best affiliation candidate.
9. Then normalize institutions.
10. Then infer countries from normalized institutions.
11. For large conferences, run raw retrieval in chunks rather than waiting for one massive run to finish.
12. Use reasoning only on downloaded raw artifacts and intermediate CSVs, keeping `UNKNOWN` when the evidence is weak.
13. Save provenance in `data/raw/<conference_slug>/<year>/collection_notes.md`.
14. Write or refresh normalized CSVs into `data/normalized/<conference_slug>/<year>/`.
15. Ensure IDs and references are internally consistent.

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
- Infer country from institution only after institution normalization.
- Prefer a multi-pass pipeline over directly writing institution and country from one mixed heuristic.
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

## Chunked Loop

For large conferences, use this loop:

1. Run the proceedings parser once to populate `papers.csv`, `authors.csv`, `paper_authors.csv`, and `papers_index.csv`.
2. Extract first-page text for a chunk of papers, for example `--start 0 --limit 100`.
3. Run `extract_affiliation_candidates.py` against the full `first_pages/` directory.
4. Run `link_author_affiliations.py`.
5. Run `normalize_institutions.py`.
6. Run `infer_countries.py`, optionally with `--use-local-llm` so the shared Ollama model only handles the remaining rows with known institution but `UNKNOWN` country.
8. Validate the dataset.
9. Repeat with the next chunk until the conference/year dataset is complete.

If you want to run the local-LLM pass manually from the console instead of through an agent, use:

```bash
make llm-country CONFERENCE_SLUG=cvpr YEAR=2016
```

For CVPR, the recommended pre-LLM preparation step after first-page extraction is:

```bash
make cvpr-prepare-llm YEAR=2018
```

For the `ICCV/ECCV` family, use the same family-level year and let `make` resolve the actual source venue:

```bash
make iccv-eccv-show-target YEAR=2024
make iccv-eccv-first-pages YEAR=2016 FIRST_PAGE_START=0 FIRST_PAGE_LIMIT=100
make iccv-eccv-first-pages-sample-2015-2016
make iccv-eccv-first-pages-sample-remaining
make iccv-eccv-prepare-llm YEAR=2024
make iccv-eccv-llm-country YEAR=2024
```

For ECCV years with several Springer books, the family first-page target now auto-discovers the linked proceedings volumes from the Springer Part I page and excludes workshop volumes. If a year ever needs an override, add a manifest at `config/proceedings_volumes/eccv/<year>.csv`; the family target will prefer that manifest automatically.

For a custom family range, use:

```bash
make iccv-eccv-first-pages-range ICCV_ECCV_START_YEAR=2017 ICCV_ECCV_END_YEAR=2025 FIRST_PAGE_START=0 FIRST_PAGE_LIMIT=100
```

The first-page extractor supports bounded parallelism. The `make` targets expose it as `FIRST_PAGE_WORKERS`, which defaults to `4`.

## Recommended Commands

For a single conference/year that already has `papers_index.csv` and extracted first-page text:

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
  --llm-review-csv data/intermediate/cvpr/2015/author_country_llm_review.csv \
  --llm-min-confidence medium
```

For CVPR years that still need proceedings parsing plus first-page extraction, you can also use:

```bash
make cvpr-first-pages YEAR=2018
make cvpr-first-pages-range CVPR_START_YEAR=2018 CVPR_END_YEAR=2025
```

Or run the wrapper:

```bash
python3 scripts/enrich_from_first_pages.py \
  --authors-csv data/normalized/cvpr/2015/authors.csv \
  --paper-authors-csv data/normalized/cvpr/2015/paper_authors.csv \
  --papers-index data/raw/cvpr/2015/papers_index.csv \
  --first-pages-dir data/raw/cvpr/2015/first_pages \
  --output-authors-csv data/normalized/cvpr/2015/authors.csv \
  --intermediate-dir data/intermediate/cvpr/2015 \
  --use-local-llm
```

## Handoff to Step 2

Once normalized datasets exist, compute country statistics with:

```bash
make stats COUNTRY=China
```

Then generate the conference-by-year overview table with:

```bash
make overview COUNTRY=China
```
