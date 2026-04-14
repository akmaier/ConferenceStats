PYTHON ?= python3
COUNTRY ?= China
INPUT_DIR ?= data/normalized
OUTPUT_DIR ?= output
CONFERENCE_SLUG ?= cvpr
YEAR ?= 2015
LLM_MIN_CONFIDENCE ?= medium
DATASET_NORMALIZED_DIR ?= data/normalized/$(CONFERENCE_SLUG)/$(YEAR)
DATASET_INTERMEDIATE_DIR ?= data/intermediate/$(CONFERENCE_SLUG)/$(YEAR)
DATASET_RAW_DIR ?= data/raw/$(CONFERENCE_SLUG)/$(YEAR)
CVPR_START_YEAR ?= 2018
CVPR_END_YEAR ?= 2025
ICCV_ECCV_START_YEAR ?= 2015
ICCV_ECCV_END_YEAR ?= 2025
FIRST_PAGE_START ?= 0
FIRST_PAGE_LIMIT ?= 0
FIRST_PAGE_WORKERS ?= 4

.PHONY: validate stats overview all llm-country cvpr-first-pages cvpr-first-pages-range cvpr-first-pages-range-sample cvpr-first-pages-status-range cvpr-prepare-llm cvpr-prepare-llm-range iccv-eccv-show-target iccv-eccv-first-pages iccv-eccv-first-pages-range iccv-eccv-first-pages-sample-2015-2016 iccv-eccv-first-pages-sample-remaining iccv-eccv-prepare-llm iccv-eccv-llm-country clean

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

cvpr-first-pages:
	$(PYTHON) scripts/collect_cvf_openaccess.py \
		--conference CVPR \
		--conference-slug cvpr \
		--year "$(YEAR)" \
		--proceedings-url "https://openaccess.thecvf.com/CVPR$(YEAR)" \
		--raw-dir "data/raw/cvpr/$(YEAR)" \
		--normalized-dir "data/normalized/cvpr/$(YEAR)"
	$(PYTHON) scripts/extract_pdf_first_pages.py \
		--papers-index "data/raw/cvpr/$(YEAR)/papers_index.csv" \
		--output-dir "data/raw/cvpr/$(YEAR)/first_pages" \
		--manifest "data/raw/cvpr/$(YEAR)/first_page_manifest.csv" \
		--start "$(FIRST_PAGE_START)" \
		--limit "$(FIRST_PAGE_LIMIT)" \
		--workers "$(FIRST_PAGE_WORKERS)"

cvpr-first-pages-range:
	year="$(CVPR_START_YEAR)"; \
	while [ "$$year" -le "$(CVPR_END_YEAR)" ]; do \
		$(MAKE) cvpr-first-pages YEAR="$$year" FIRST_PAGE_START="$(FIRST_PAGE_START)" FIRST_PAGE_LIMIT="$(FIRST_PAGE_LIMIT)" FIRST_PAGE_WORKERS="$(FIRST_PAGE_WORKERS)"; \
		year=$$((year + 1)); \
	done

cvpr-first-pages-range-sample:
	$(MAKE) cvpr-first-pages-range \
		CVPR_START_YEAR=2018 \
		CVPR_END_YEAR=2025 \
		FIRST_PAGE_START=0 \
		FIRST_PAGE_LIMIT=100

cvpr-first-pages-status-range:
	$(PYTHON) scripts/report_first_page_status.py \
		--conference-slug cvpr \
		--start-year "$(CVPR_START_YEAR)" \
		--end-year "$(CVPR_END_YEAR)"

cvpr-prepare-llm:
	$(PYTHON) scripts/enrich_from_first_pages.py \
		--authors-csv "data/normalized/cvpr/$(YEAR)/authors.csv" \
		--paper-authors-csv "data/normalized/cvpr/$(YEAR)/paper_authors.csv" \
		--papers-index "data/raw/cvpr/$(YEAR)/papers_index.csv" \
		--first-pages-dir "data/raw/cvpr/$(YEAR)/first_pages" \
		--output-authors-csv "data/normalized/cvpr/$(YEAR)/authors.csv" \
		--intermediate-dir "data/intermediate/cvpr/$(YEAR)"

cvpr-prepare-llm-range:
	year="$(CVPR_START_YEAR)"; \
	while [ "$$year" -le "$(CVPR_END_YEAR)" ]; do \
		$(MAKE) cvpr-prepare-llm YEAR="$$year"; \
		year=$$((year + 1)); \
	done

iccv-eccv-show-target:
	slug="$$(if [ $$(( $(YEAR) % 2 )) -eq 0 ]; then echo eccv; else echo iccv; fi)"; \
	conf="$$(if [ $$(( $(YEAR) % 2 )) -eq 0 ]; then echo ECCV; else echo ICCV; fi)"; \
	url="$$( $(PYTHON) scripts/get_conference_field.py --conference-slug $$slug --year "$(YEAR)" --field proceedings_url )"; \
	echo "family=ICCV/ECCV"; \
	echo "year=$(YEAR)"; \
	echo "conference=$$conf"; \
	echo "conference_slug=$$slug"; \
	echo "proceedings_url=$$url"

iccv-eccv-first-pages:
	slug="$$(if [ $$(( $(YEAR) % 2 )) -eq 0 ]; then echo eccv; else echo iccv; fi)"; \
	conf="$$(if [ $$(( $(YEAR) % 2 )) -eq 0 ]; then echo ECCV; else echo ICCV; fi)"; \
	url="$$( $(PYTHON) scripts/get_conference_field.py --conference-slug $$slug --year "$(YEAR)" --field proceedings_url )"; \
	volumes_csv="config/proceedings_volumes/$$slug/$(YEAR).csv"; \
	if [ "$$slug" = "iccv" ]; then \
		$(PYTHON) scripts/collect_cvf_openaccess.py \
			--conference "$$conf" \
			--conference-slug "$$slug" \
			--year "$(YEAR)" \
			--proceedings-url "$$url" \
			--raw-dir "data/raw/$$slug/$(YEAR)" \
			--normalized-dir "data/normalized/$$slug/$(YEAR)"; \
	else \
		if [ -f "$$volumes_csv" ]; then \
			$(PYTHON) scripts/collect_springer_proceedings.py \
				--conference "$$conf" \
				--conference-slug "$$slug" \
				--year "$(YEAR)" \
				--volumes-csv "$$volumes_csv" \
				--raw-dir "data/raw/$$slug/$(YEAR)" \
				--normalized-dir "data/normalized/$$slug/$(YEAR)"; \
		else \
			$(PYTHON) scripts/collect_springer_proceedings.py \
				--conference "$$conf" \
				--conference-slug "$$slug" \
				--year "$(YEAR)" \
				--proceedings-url "$$url" \
				--raw-dir "data/raw/$$slug/$(YEAR)" \
				--normalized-dir "data/normalized/$$slug/$(YEAR)"; \
		fi; \
	fi; \
	$(PYTHON) scripts/extract_pdf_first_pages.py \
		--papers-index "data/raw/$$slug/$(YEAR)/papers_index.csv" \
		--output-dir "data/raw/$$slug/$(YEAR)/first_pages" \
		--manifest "data/raw/$$slug/$(YEAR)/first_page_manifest.csv" \
		--start "$(FIRST_PAGE_START)" \
		--limit "$(FIRST_PAGE_LIMIT)" \
		--workers "$(FIRST_PAGE_WORKERS)"

iccv-eccv-first-pages-range:
	year="$(ICCV_ECCV_START_YEAR)"; \
	while [ "$$year" -le "$(ICCV_ECCV_END_YEAR)" ]; do \
		$(MAKE) iccv-eccv-first-pages YEAR="$$year" FIRST_PAGE_START="$(FIRST_PAGE_START)" FIRST_PAGE_LIMIT="$(FIRST_PAGE_LIMIT)" FIRST_PAGE_WORKERS="$(FIRST_PAGE_WORKERS)"; \
		year=$$((year + 1)); \
	done

iccv-eccv-first-pages-sample-2015-2016:
	for year in 2015 2016; do \
		$(MAKE) iccv-eccv-first-pages YEAR="$$year" FIRST_PAGE_START=0 FIRST_PAGE_LIMIT=100; \
	done

iccv-eccv-first-pages-sample-remaining:
	$(MAKE) iccv-eccv-first-pages-range \
		ICCV_ECCV_START_YEAR=2017 \
		ICCV_ECCV_END_YEAR=2025 \
		FIRST_PAGE_START=0 \
		FIRST_PAGE_LIMIT=100

iccv-eccv-prepare-llm:
	slug="$$(if [ $$(( $(YEAR) % 2 )) -eq 0 ]; then echo eccv; else echo iccv; fi)"; \
	$(PYTHON) scripts/enrich_from_first_pages.py \
		--authors-csv "data/normalized/$$slug/$(YEAR)/authors.csv" \
		--paper-authors-csv "data/normalized/$$slug/$(YEAR)/paper_authors.csv" \
		--papers-index "data/raw/$$slug/$(YEAR)/papers_index.csv" \
		--first-pages-dir "data/raw/$$slug/$(YEAR)/first_pages" \
		--output-authors-csv "data/normalized/$$slug/$(YEAR)/authors.csv" \
		--intermediate-dir "data/intermediate/$$slug/$(YEAR)"

iccv-eccv-llm-country:
	slug="$$(if [ $$(( $(YEAR) % 2 )) -eq 0 ]; then echo eccv; else echo iccv; fi)"; \
	$(PYTHON) scripts/infer_countries.py \
		--authors-csv "data/normalized/$$slug/$(YEAR)/authors.csv" \
		--output-authors-csv "data/normalized/$$slug/$(YEAR)/authors.csv" \
		--output-countries-csv "data/intermediate/$$slug/$(YEAR)/author_countries.csv" \
		--use-local-llm \
		--llm-review-csv "data/intermediate/$$slug/$(YEAR)/author_country_llm_review.csv" \
		--llm-min-confidence "$(LLM_MIN_CONFIDENCE)"

clean:
	rm -f "$(OUTPUT_DIR)/country_stats.csv" "$(OUTPUT_DIR)/country_stats.md" \
		"$(OUTPUT_DIR)/country_overview.csv" "$(OUTPUT_DIR)/country_overview.md"
