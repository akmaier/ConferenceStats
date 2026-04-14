PYTHON ?= python3
COUNTRY ?= China
INPUT_DIR ?= data/normalized
OUTPUT_DIR ?= output
CONFERENCE_SLUG ?= cvpr
YEAR ?= 2015
LLM_MIN_CONFIDENCE ?= medium
DATASET_NORMALIZED_DIR ?= data/normalized/$(CONFERENCE_SLUG)/$(YEAR)
DATASET_INTERMEDIATE_DIR ?= data/intermediate/$(CONFERENCE_SLUG)/$(YEAR)

.PHONY: validate stats overview all llm-country clean

validate:
	$(PYTHON) scripts/validate_collection.py --input-dir "$(INPUT_DIR)"

stats:
	$(PYTHON) scripts/compute_country_stats.py \
		--input-dir "$(INPUT_DIR)" \
		--country "$(COUNTRY)" \
		--output-csv "$(OUTPUT_DIR)/country_stats.csv" \
		--output-md "$(OUTPUT_DIR)/country_stats.md"

overview:
	$(PYTHON) scripts/build_overview_table.py \
		--input-csv "$(OUTPUT_DIR)/country_stats.csv" \
		--country "$(COUNTRY)" \
		--output-csv "$(OUTPUT_DIR)/country_overview.csv" \
		--output-md "$(OUTPUT_DIR)/country_overview.md"

all: stats overview

llm-country:
	$(PYTHON) scripts/infer_countries.py \
		--authors-csv "$(DATASET_NORMALIZED_DIR)/authors.csv" \
		--output-authors-csv "$(DATASET_NORMALIZED_DIR)/authors.csv" \
		--output-countries-csv "$(DATASET_INTERMEDIATE_DIR)/author_countries.csv" \
		--use-local-llm \
		--llm-review-csv "$(DATASET_INTERMEDIATE_DIR)/author_country_llm_review.csv" \
		--llm-min-confidence "$(LLM_MIN_CONFIDENCE)"

clean:
	rm -f "$(OUTPUT_DIR)/country_stats.csv" "$(OUTPUT_DIR)/country_stats.md" \
		"$(OUTPUT_DIR)/country_overview.csv" "$(OUTPUT_DIR)/country_overview.md"
