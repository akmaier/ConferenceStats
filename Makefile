PYTHON ?= python3
COUNTRY ?= China
INPUT_DIR ?= data/normalized
OUTPUT_DIR ?= output

.PHONY: validate stats overview all clean

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

clean:
	rm -f "$(OUTPUT_DIR)/country_stats.csv" "$(OUTPUT_DIR)/country_stats.md" \
		"$(OUTPUT_DIR)/country_overview.csv" "$(OUTPUT_DIR)/country_overview.md"
