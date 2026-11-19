# Addendum 1 (18 November 2026, before any segmentation output was produced)

Pre-run level check (PLAN technical gate) found that TRIDENT's HEST segmenter at 10x reads a different pyramid level on each scanner:

- KR_AT2 (0.2532 µm/px): wanted downsample 3.95, level 1 (4.0) is within the 0.1 tolerance, so it reads level 1.
- KR_GT450 (0.2621 µm/px): wanted downsample 3.82, level 1 (4.0) is outside tolerance, so it reads full-resolution level 0 and resizes by 3.82.

GrandQC (1x) and Otsu (1.25x) read reduced levels on both scanners.

Our local GT450 copies lack most level-0 tile bytes, so HEST on GT450 would fail the gate. Change: download the 13 complete GT450 files from the PLISM figshare record (article 24988074, ndownloader URLs in HUMAN_SCANNER_REPLICATION_20261110/files_24988074.json), verify each against figshare's computed MD5, store them under /Volumes/Temp_flex/parallax_pathology/TRIDENT_PLISM_20261118/full/, and run every arm on: AT2 = existing local copies (all levels TRIDENT reads are complete; gate still checked), GT450 = complete files. PLISM_01 is not modified.

The level choice itself is recorded as a reading (which level each segmenter reads per scan), since it is a scanner-dependent code path. Readings, rule and arms are otherwise unchanged.
