# Colour-profile rerun (added in v1.1.0, 25 November 2026)

Both scanners embed an ICC colour profile in the file: "AT2" in the AT2 scans, "Segue_v2" in the GT450 scans. TRIDENT reads pixels through OpenSlide without applying it. After the HistoQC maintainer suggested applying the profile ([choosehappy/HistoQC#343](https://github.com/choosehappy/HistoQC/issues/343)), we reran every arm of this study with one change: a run-time wrapper on `openslide.OpenSlide.read_region` that converts each region from the slide's own profile to sRGB (Pillow ImageCms / LittleCMS, perceptual intent, alpha kept). Thumbnails go through the same call. TRIDENT c07bf25 (unedited), the weights, settings, fields and scoring are the same as in the main study.

| segmenter | fields that switch (of 156), default read | profile applied | AT2-only / GT450-only, profile applied |
|---|---|---|---|
| HEST (default) | 6 | 0 | 0 / 0 |
| GrandQC | 1 | 0 | 0 / 0 |
| Otsu | 28 | 4 | 2 / 2 |
| HEST + artifact removal | 26 | 53 | 6 / 47 |

For the three segmenters, most of the scanner difference comes from the unapplied profile. Artifact removal goes the other way. HEST alone switches no field with the profile applied, so the added switches come from the artifact step: pooled over the 13 sections, it keeps 68% of HEST's AT2 region (86% on the default read) and 92% of the GT450 region (88%), and its AT2 share is lower than on the default read in 12 of 13 sections. HR is the exception: there the step keeps 106.6 mm² on AT2 and 166.3 mm² on GT450, against 20.6 and 40.9 on the default read.

**Gate.** Before the converted arms, Otsu and GrandQC were run with the same wrapper and the conversion switched off. All 26 regions of each are identical to the main study's (zero symmetric difference), so the wrapper alone changes nothing.

**Check.** `python3 reproduce.py` at the repository root recomputes all of the above from the stored regions, including the gate, and prints `ALL MATCH`.

## Contents

- `PLAN.md`: written and frozen before any run in this rerun (SHA-256 in `PLAN.sha256`, time in `PLAN.frozen_at.txt`; the first run started 41 seconds later).
- `regions/<arm>/<scan>.geojson.gz`: TRIDENT's own `contours_geojson` output, gzipped, unmodified. Arms: `gate_otsu`, `gate_grandqc` (conversion off), `icc_otsu`, `icc_grandqc`, `icc_hest`, `icc_hest_artifacts` (conversion on).
- `run_meta/<arm>/`: as in the main study, plus `convert`, the number of `read_region` calls and the profile descriptions applied. Local paths are reduced to file names.
- `results/`: `gate.json`, `summary.json`, `sections.csv`, `fields.csv`, `scans.csv`, in the same formats as the main study's.
- `scripts/`: the scripts as run. `run_chain.sh` ran the arms in the planned order (from the top of the working folder), `02_segment_icc.py` is `../scripts/02_segment.py` with the wrapper added, `gate_check.py` the gate, `03_score_icc.py` the scoring, `04_labbook_icc.py` the lab book. Like the main study's scripts, they document the run and expect local slides and a TRIDENT checkout.
- `brightness/`: `thumbnail_check.py` and its output, median tissue brightness (0 to 255) on 2000-pixel OpenSlide thumbnails of each scan, without and with the profile. Without it, AT2 is darker on all 13 sections (median gap 40.5); with it, AT2 is brighter on all 13 (median gap 6.9). This needs the slides and is not part of `reproduce.py`. It was run for the HistoQC rerun and is copied here unchanged.
- `LABBOOK.html`: the rerun's lab book. Its paths refer to the original working folders (`../trident-plism` is the main study, `../plism-icc` the HistoQC rerun).

## Scope

One rendering intent. Descriptive, like the main study: it does not say which input is right. We don't know what colour handling the segmentation and artifact models saw in training, so a converted image is not assumed to be closer to their training data.
