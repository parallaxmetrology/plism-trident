# TRIDENT tissue segmentation on paired PLISM scans (AT2 vs GT450)

The same 13 H&E tissue-array sections, each scanned on Aperio AT2 and Aperio GT450, run through the tissue segmenters in [TRIDENT](https://github.com/mahmoodlab/TRIDENT) at their command-line defaults. The tissue is fixed; only the scanner changes. On 156 registered 128 µm fields (12 per section, the same physical location on both scans), a field counts as admitted on a scanner when at least half of it lies inside the tissue region. That rule is ours, not TRIDENT's.

| segmenter | fields that switch (of 156) | AT2-only / GT450-only | median GT450/AT2 tissue area |
|---|---|---|---|
| HEST (default) | 6 | 3 / 3 | 0.978 |
| GrandQC | 1 | 0 / 1 | 0.992 |
| Otsu | 28 | 18 / 10 | 0.933 |
| HEST + artifact removal | 26 | 10 / 16 | 0.998 |

For context, HistoQC's default pipeline switched 52 of the same 156 fields ([parallaxmetrology/plism-histoqc](https://github.com/parallaxmetrology/plism-histoqc)).

Open **LABBOOK.html** for the full record: plan and addenda, technical gate, per-section tables, switched fields, contour overlays, secondary readings, deviations and scope. Discussion upstream: [mahmoodlab/TRIDENT#250](https://github.com/mahmoodlab/TRIDENT/issues/250).

## Reproduce the tables

With Python 3.10 or newer, numpy and shapely 2:

    python3 reproduce.py

This reads the stored TRIDENT regions (`regions/`), the field polygons (`fields/`) and the recorded resolutions (`run_meta/`), and recomputes every field fraction and decision, every section area and the switch counts. It also confirms that the two repeat runs are identical to the first runs and that `PLAN.md` and the addenda match their recorded SHA-256. It prints `ALL MATCH` and exits 0 when everything agrees with `results/`. No slides, GPU or TRIDENT install are needed; it takes about 20 seconds.

## Contents

- `PLAN.md`: written and frozen (SHA-256 in `PLAN.sha256`, time in `PLAN.frozen_at.txt`) before any TRIDENT segmentation of these scans. `ADDENDUM_1-3.md` record the later changes: full GT450 downloads, data-loader workers, and a run-time device patch for the artifact step.
- `regions/<arm>/<scan>.geojson.gz`: TRIDENT's own `contours_geojson` output, gzipped, unmodified. Coordinates are level-0 pixels of each scan; the `EPSG:3857` tag in each file is TRIDENT's default label, not a map projection. Arms: `hest`, `grandqc`, `otsu`, `hest_artifacts`, plus `hest_repeat` (KR, both scanners) and `hest_artifacts_repeat` (HR and MY, both scanners).
- `fields/<section>.json`: the 12 registered fields per section, as native level-0 pixel-centre polygons for AT2 (first) and GT450 (second); the same fields as the HistoQC study.
- `run_meta/<arm>/`: device, timing, software versions, TRIDENT commit, and per scan the resolution, pyramid level and downsample TRIDENT used. Local paths are reduced to file names.
- `results/`: `fields.csv` (every field, every arm), `sections.csv`, `scans.csv`, `summary.json`, `checks.json` (second-pass checks), `brightness.csv`, `artifact_repeat.json`.
- `scripts/`: the scripts as run. `01` downloads the GT450 files, `02` runs TRIDENT, `03` scores, `04` builds the lab book, `05` runs the second-pass checks, `06` draws the artifact overlay figure, `07` compares the artifact repeat. They expect the slides and a TRIDENT checkout at local paths, so they document the run rather than run here as they stand; `reproduce.py` is the portable check.
- `LABBOOK.html`: self-contained record of the study. Its file list describes the original working folder (job folders, logs, issue drafts); this repository carries the parts listed here.
- `figs/`: contour overlay figures. `weights.sha256`: SHA-256 of the three model weight files used.

## Running the segmentation yourself

TRIDENT at commit `c07bf25b9ad937bc6c8af8ea4ef16eb9979bbe8a`, torch 2.15.0, OpenSlide 4.0.1, Python 3.11.17; HEST and GrandQC on Apple MPS, Otsu on CPU. TRIDENT is not included here (its licence is CC BY-NC-ND 4.0); clone it from its own repository at that commit. `scripts/02_segment.py` calls `Processor.run_segmentation_job` with the arguments `run_batch_of_slides.py --task seg` uses. For the artifact arm only, it sets the device for the artifact model's `segment_tissue` call at run time, because at that commit the call does not receive the requested device (see `ADDENDUM_3.md` and mahmoodlab/TRIDENT#237). TRIDENT's source is not edited.

## Sources and licences

- Images: PLISM, Original Whole Slide Images Dataset, version 1, Mieko Ochi, Daisuke Komura, Takumi Onoyama and Shumpei Ishikawa, https://doi.org/10.25452/figshare.plus.24988074.v1, CC BY 4.0. Contour overlays in `figs/` and the lab book are adapted from these images.
- Segmentation: TRIDENT, Mahmood Lab, https://github.com/mahmoodlab/TRIDENT, CC BY-NC-ND 4.0. The regions in `regions/` are its outputs on the images above.

Code in this repository is MIT licensed (see LICENSE). Images and contour overlays derived from PLISM keep its CC BY 4.0 terms; TRIDENT is not included and keeps its own licence.

## Scope

One tissue array, two scanners from one vendor, 13 serial and differently stained sections from shared tissue. Descriptive only. Neither scanner nor any segmenter is taken as correct: a change between scanners says which tool is sensitive here, not which region is right.

Rus Parrish, Parallax Metrology (https://parallaxmetrology.com)
