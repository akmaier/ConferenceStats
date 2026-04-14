# CVPR 2015 Collection Notes

- Conference: CVPR
- Year: 2015
- Proceedings URL: https://openaccess.thecvf.com/CVPR2015
- Collection status: script-driven in-progress collection

## Scope

This dataset was generated with the script-first step-1 workflow.

Included in this run:

- full proceedings table of contents parsing from the CVF open access page
- all 602 paper titles from the proceedings page
- ordered author lists for all 602 papers
- paper page URLs and PDF URLs in the raw index
- incremental first-page text extraction for affiliation and country enrichment
- partial institution and country enrichment from local first-page text files

Not yet fully resolved:

- noisy or truncated affiliation strings in some first-page texts
- country inference for industry-only or otherwise ambiguous affiliations

## Counts

- Papers collected: 602
- Author records collected: 2207

## Current Progress

- proceedings parse: complete
- first-page extraction: complete for all 602 papers
- institution enrichment: 1721 of 2207 author rows currently non-`UNKNOWN`
- country enrichment: 783 of 2207 author rows currently non-`UNKNOWN`
- enrichment quality improvement: still in progress

## Notes

- Proceedings parsing was done by `scripts/collect_cvf_openaccess.py`.
- First-page extraction is being done by `scripts/extract_pdf_first_pages.py`.
- Affiliation and country enrichment is being done by `scripts/enrich_from_first_pages.py`.
- `papers_index.csv` contains the paper and PDF URLs needed by downstream raw-data retrieval scripts.
- Several industry affiliations remain `UNKNOWN` at the country level when the first-page text does not provide clear geographic evidence.
- Some affiliations still include parser noise such as emails, abbreviated departments, or broken line merges and may need another cleanup pass.
