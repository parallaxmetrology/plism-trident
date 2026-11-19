# Addendum 2 (18 November 2026, execution detail, before any arm was run)

The first smoke test (GrandQC on KR_AT2) crashed: a DataLoader worker died with a segmentation fault under TRIDENT's fork fallback on macOS. All runs use `Processor(max_workers=0)`, i.e. single-process tile loading (`get_num_workers` returns 0). This changes speed only, not which tiles are read or how. The smoke output (out/smoke_grandqc) is a pipeline check and is not used in any reading.

Later the same day (before the HEST GT450 and artifact arms ran): to allow running without a network connection, `TRIDENT/trident/segmentation_models/local_ckpts.json` was filled with the paths of the already-downloaded checkpoints (TRIDENT's documented offline route). Same files as the online path would fetch; SHA-256 in weights.sha256. Earlier arms loaded the same files via snapshot_download.
