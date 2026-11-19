# Addendum 3: device for the artifact-removal step (secondary arm only)

Written 19 November 2026, after the primary arms finished and before any `hest_artifacts` output existed.

The first `hest_artifacts` run stopped on its first slide with `AssertionError: Torch not compiled with CUDA enabled` (logs/hest_artifacts_*_failed_cuda.txt). Cause, in TRIDENT at the pinned commit: `Processor.run_segmentation_job` (trident/Processor.py, the `artifact_remover_model` branch) calls `wsi.segment_tissue` for the artifact model without passing `device` or `batch_size`, so that call uses the method defaults `device='cuda:0'` and `batch_size=16` whatever the caller asked for.

Change: for this arm only, `scripts/02_segment.py` wraps `WSI.segment_tissue` at run time so that a call without `device` gets the run's device (MPS). TRIDENT source is not edited. `batch_size` is left at 16, which is what the CLI also produces for this step. The partial output directory from the failed run was deleted before the rerun. Primary arms and readings are unchanged.

This behaviour is itself recorded as a finding for the issue draft.
