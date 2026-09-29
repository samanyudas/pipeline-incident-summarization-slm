# PHMSA source and usage review

Reviewed September 27, 2026.

## Publisher license evidence

The [official Data.gov catalog record](https://catalog.data.gov/dataset/gas-distribution-gas-transmission-gathering-lng-incidents-and-hazardous-liquid-accident-an) identifies PHMSA as publisher and supplies a public-domain license label.
Its distribution URL and agency data-series URL point to the same [PHMSA landing page](https://www.phmsa.dot.gov/data-and-statistics/pipeline/distribution-transmission-gathering-lng-and-liquid-accident-and-incident-data) that lists the Type R archive.
The catalog identifier is 34.2 and its metadata modification date is September 17, 2026.
This is stronger evidence than public downloading availability alone and supersedes the earlier finding that no license evidence had been located.

The license URL is `http://www.usa.gov/publicdomain/label/1.0/`.
Following its HTTPS equivalent redirects to [USAGov copyright guidance](https://www.usa.gov/government-copyright), rather than a separate license instrument.
That guidance distinguishes federal works from third-party material and discusses privacy, endorsement, and international scope.
The series-level publisher designation is the documented reuse basis for this local feasibility project.
Treating training as reuse under that designation is a project inference, not an express PHMSA approval of model training or this model.
No separate Type R-specific training license or direct agency confirmation was found.
No commercial deployment or dataset publication has occurred.
The project continues to keep source records, targets, and adapters local.
The record does not claim a legal guarantee for every downstream jurisdiction or use.

## Acquisition record

The user identified the source landing page.
`source_record.json` records the direct ZIP URL and fingerprints of the existing local table and field-guide PDF.
macOS metadata records the table's date added as September 26, 2026 at 10:08:25 UTC, but has no downloaded-date or origin-URL value.
Date added is not proof of download date, so downloaded_at remains null.

To reproduce acquisition, use the ZIP link in `source_record.json`, save it to a new local raw-data directory, and extract the table and field guide there.
Record the actual retrieval timestamp and the ZIP hash when downloading.
Compare each extracted file's SHA-256 with the source record before using it with existing manifests.
The URL is a rolling dataset, so a later download may differ from the project snapshot.
Preserve the old snapshot and version changed data separately.
Do not overwrite evaluation manifests to make a changed source pass validation.
