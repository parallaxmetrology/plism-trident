# Plan: TRIDENT on paired PLISM scans with embedded ICC profiles applied

Written and frozen 24 November 2026, before any run in this folder. Follows the HistoQC ICC rerun (`../plism-icc`), where applying each scan's embedded profile cut field switches from 52 to 5.

## Question

TRIDENT, like HistoQC, reads pixels without applying the scan's embedded ICC profile ("AT2" in the AT2 files, "Segue_v2" in the GT450 files). If every region TRIDENT reads is first converted from the scan's own profile to sRGB, how many of the 156 registered fields switch admission between the two scanners, for each segmenter? The original TRIDENT study (`../trident-plism`, no conversion) found HEST 6, GrandQC 1, Otsu 28, HEST with artifact removal 26.

## Known before this plan

The HistoQC ICC result above, and the thumbnail brightness check (median AT2/GT450 tissue-luma gap 40.5 without profiles, 6.9 with). No TRIDENT region has been computed with a profile applied. No direction or size of change is predicted for any segmenter.

## Everything held fixed

As in `../trident-plism/PLAN.md` and its addenda: the 26 scans (`data/slides`, linked in place; AT2 range-acquired copies read only at reduced levels, enforced by the same level check), TRIDENT at c07bf25 (linked in place, unedited), the same weights (`../trident-plism/weights.sha256`), the same segmenter settings (confidence 0.5, holes as tissue, batch 64, data-loader workers 0), HEST and GrandQC on MPS, Otsu on CPU, the artifact arm's run-time device patch (Addendum 3), the same 156 fields and the same scoring (`03_score.py` logic, admitted at a field fraction of 0.50 or more).

## The one change

`openslide.OpenSlide.read_region` is wrapped at run time. Each region is converted from that slide's embedded profile to sRGB with Pillow ImageCms (LittleCMS), perceptual intent, on the RGB channels; alpha is kept. `get_thumbnail` uses the same method. Segmentation model weights and preprocessing are unchanged.

## Gate

With the same wrapper and the conversion switched off (`gate_otsu`, `gate_grandqc`), all 26 regions of each must equal the original study's regions (zero symmetric difference). This shows the wrapper alone changes nothing. HEST's run-to-run identity was already shown in the original study (KR repeat) and on the artifact arm (HR and MY repeat). If the gate fails, stop and report.

## Arms and readings

Arms, in order: `icc_otsu`, `icc_grandqc`, `icc_hest`, `icc_hest_artifacts`.

1. Primary, per arm: fields switched of 156 (AT2-only / GT450-only), beside the original count.
2. Secondary, per arm: median GT450/AT2 tissue area over 13 sections and its range; regions below 10% of their pair; fields admitted per scanner; fields whose decision changes from the original run, per scanner.
3. Secondary: HR tissue areas per arm.

## Scope

Same array, scanners, software and settings; only the colour conversion changes. One rendering intent. Descriptive; it does not say which region is right. Segmentation models were trained on images whose colour handling is not known here, so a converted image is not assumed to be closer to their training data.
