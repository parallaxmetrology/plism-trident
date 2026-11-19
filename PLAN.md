# Same tissue, two scanners: TRIDENT tissue segmentation on paired PLISM scans

Plan written 18 November 2026, before any TRIDENT segmentation of these scans. Frozen by SHA-256 in PLAN.sha256.

## Question

TRIDENT (mahmoodlab/TRIDENT) offers three tissue segmenters: HEST (default, DeepLabV3 at 10x), GrandQC (UNet++ at 1x) and Otsu (classical, 1.25x). When the tissue is fixed and only the scanner changes, how much does each segmenter's tissue region change? This repeats the 11-12 November HistoQC test (choosehappy/HistoQC#343, parallaxmetrology/plism-histoqc) on a second, widely used tool.

## Material (reused, unchanged)

- 26 scans: 13 PLISM H&E tissue-array sections (Ochi et al., CC BY 4.0), each on Aperio AT2 and GT450. Local copies at `/Volumes/Temp_flex/parallax_pathology/HISTOQC_PAIRED_SELECTION_20261111/PLISM_01/sources/`. They hold every reduced-resolution level and associated image byte-for-byte; only unused full-resolution tiles are absent (range receipts beside each file).
- 156 registered 128 µm fields (12 per section), native level-0 polygons for both scanners in `PLISM_01/maps/*.json`, unchanged from the HistoQC study.
- Nothing is copied or edited in PLISM_01; it is read in place.

## Software

- TRIDENT at commit c07bf25b9ad937bc6c8af8ea4ef16eb9979bbe8a (18 Nov 2026), installed editable in `.venv` (Python 3.11).
- Weights from MahmoodLab/hest-tissue-seg on Hugging Face (ungated): Tissue_Detection_MPP10.pth / deeplabv3_seg_v4.ckpt (HEST), GrandQC_MPP1_state_dict.pth (GrandQC). File SHA-256 recorded at run time.
- Segmentation through `Processor.run_segmentation_job` with the same arguments `run_batch_of_slides.py --task seg` passes by default: `seg_mag = segmentation_model.target_mag`, `seg_conf_thresh 0.5`, `holes_are_tissue True`, no artifact or pen removal, batch size 64. The only change from the CLI is the device: Apple MPS for HEST and GrandQC (the CLI assumes CUDA); Otsu on CPU as in the CLI. One device for all 26 scans of a segmenter.

## Arms

Primary: `hest`, `grandqc`, `otsu`, each at defaults, all 26 scans.
Secondary (reported, not primary): `hest` with `--remove_artifacts` (GrandQC artifact model at 10x).

## Technical gate

- A run is valid only if no full-resolution (level-0) tile is read. Checked by recording the OpenSlide level the patcher and thumbnail use (expected: a reduced level) and by a pixel check that no read region is all-zero image data where the range receipt says level-0 tiles were omitted. A failure is reported as technical, not as a result.
- Repeatability: KR_AT2 and KR_GT450 segmented twice with HEST; contour areas must agree to within 0.1%. If not, report the spread and use the first run.

## Readings

Tissue region = union of the polygons in TRIDENT's `contours_geojson/<slide>.geojson` (level-0 pixel coordinates).

1. **Field decisions (primary).** For each field and scanner, fraction of the field polygon's area inside the tissue region (exact polygon intersection). Admitted if ≥ 0.50 (ties admitted), the same rule as the HistoQC study. Per segmenter: number of the 156 fields that switch (AT2-only, GT450-only), and the mean over the 13 sections of the per-section switch fraction.
2. **Tissue area.** Per scan, tissue region area in mm² (level-0 mpp from the slide header). Per segmenter: GT450/AT2 ratio per section, its median, and how many of 13 are smaller on GT450.
3. **Empty or near-empty regions.** Any scan whose region is empty or below 10% of its pair is listed.
4. **Context, not a test.** HistoQC default numbers from the earlier study (52 of 156 switched; GT450 usable tissue median 6.5% of AT2) shown beside these, from its published tables.

Secondary, descriptive: the effective minimum piece size in `mask_to_gdf` (`min_contour_area=1000` scaled by level-0 mpp² against a contour area measured on a mask resized to 2000 rows) converted to mm² per scan, to show whether it differs between the paired scans.

## Scope and what is not claimed

One tissue array, two scanners from one vendor, 13 serial and differently stained sections from shared tissue. Descriptive only; no independent-patient inference. Neither scanner nor any segmenter is taken as correct; a change between scanners says which tool is sensitive here, not which mask is right. The field rule is ours, not TRIDENT's (TRIDENT's own patching uses `min_tissue_proportion`, default 0). No private Parallax measurements are used.

## Outputs

`out/<arm>/` (TRIDENT job dirs), `results/fields.csv`, `results/sections.csv`, `results/summary.json`, `LABBOOK.html`, and, only after review, `ISSUE_DRAFT.md`. Nothing is posted without Russell's go-ahead.
