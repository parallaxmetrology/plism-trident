"""TRIDENT tissue segmentation as in trident-plism/scripts/02_segment.py, with the ICC conversion of PLAN.md.
Usage: 02_segment_icc.py ARM [slide names...]
  ARM in gate_otsu, gate_grandqc (wrapper on, conversion OFF: must reproduce the original regions)
         icc_hest, icc_grandqc, icc_otsu, icc_hest_artifacts (every read_region converted from the embedded profile to sRGB)
"""
import sys, json, hashlib, os, time, platform
from pathlib import Path
import torch, openslide
ROOT = Path(__file__).resolve().parents[1]
SLIDES = ROOT / 'data' / 'slides'
arm = sys.argv[1]
names = sys.argv[2:] or sorted(p.name for p in SLIDES.glob('*.svs'))
if names in (['AT2'], ['GT450']):
    names = sorted(p.name for p in SLIDES.glob(f'*_{names[0]}.svs'))
assert names and all(n.endswith('.svs') and ' ' not in n for n in names), names
base = arm.split('_', 1)[1]
assert arm.split('_', 1)[0] in ('gate', 'icc') and base in ('hest', 'grandqc', 'otsu', 'hest_artifacts'), arm
seg = {'hest': 'hest', 'grandqc': 'grandqc', 'otsu': 'otsu', 'hest_artifacts': 'hest'}[base]
CONVERT = arm.startswith('icc_')

# PLAN.md: wrap OpenSlide.read_region at run time (TRIDENT source untouched). get_thumbnail calls it too.
import openslide as _os
from PIL import ImageCms
_SRGB = ImageCms.createProfile('sRGB')
_orig_read = _os.OpenSlide.read_region
def _read(self, location, level, size):
    im = _orig_read(self, location, level, size)
    _calls[0] += 1
    if not CONVERT:
        return im
    xf = getattr(self, '_icc_xf', None)
    if xf is None:
        prof = self.color_profile
        assert prof is not None, 'no embedded profile'
        xf = self._icc_xf = ImageCms.buildTransform(prof, _SRGB, 'RGB', 'RGB', renderingIntent=ImageCms.Intent.PERCEPTUAL)
        _profiles.append(ImageCms.getProfileDescription(prof).strip())
    rgb = ImageCms.applyTransform(im.convert('RGB'), xf)
    rgb.putalpha(im.getchannel('A'))
    return rgb
_calls = [0]; _profiles = []
_os.OpenSlide.read_region = _read
device = 'cpu' if seg == 'otsu' else ('mps' if torch.backends.mps.is_available() else 'cpu')
job = ROOT / 'out' / arm
job.mkdir(parents=True, exist_ok=True)

from trident import Processor, load_wsi
from trident.segmentation_models.load import segmentation_model_factory
model = segmentation_model_factory(seg, confidence_thresh=0.5)
remover = segmentation_model_factory('grandqc_artifact', remove_penmarks_only=False) if base == 'hest_artifacts' else None

# Level each reader will use (same rule as WSIPatcher._prepare, tolerance 0.1)
levels = {}
for n in names:
    w = load_wsi(str(SLIDES / n), lazy_init=False)
    ds = (10 / model.target_mag) / w.mpp
    lv, cds = w.get_best_level_and_custom_downsample(ds, tolerance=0.1)
    levels[n] = dict(mpp=w.mpp, dims=list(w.dimensions), level_downsamples=[float(x) for x in w.level_downsamples],
                     seg_mag=model.target_mag, wanted_downsample=ds, level=int(lv), custom_downsample=float(cds),
                     real_path=os.path.realpath(SLIDES / n))
    if 'PLISM_01/sources' in levels[n]['real_path']:
        assert lv > 0, f'{n}: level 0 would be read from a range-acquired copy'
    if remover is not None:
        ds2 = (10 / remover.target_mag) / w.mpp
        levels[n]['artifact_level'] = int(w.get_best_level_and_custom_downsample(ds2, tolerance=0.1)[0])
        if 'PLISM_01/sources' in levels[n]['real_path']:
            assert levels[n]['artifact_level'] > 0

if remover is not None:
    # ADDENDUM_3: Processor.run_segmentation_job calls segment_tissue for the artifact model without
    # device/batch_size, so it falls back to device='cuda:0', batch 16. Patch only the device default
    # at run time (TRIDENT source untouched); batch 16 is kept, as the CLI would use it.
    import functools
    from trident.wsi_objects.WSI import WSI
    _orig = WSI.segment_tissue
    @functools.wraps(_orig)
    def _seg(self, *a, **k):
        k.setdefault('device', device)
        return _orig(self, *a, **k)
    WSI.segment_tissue = _seg

proc = Processor(job_dir=str(job), wsi_source=str(SLIDES), wsi_ext=['.svs'], skip_errors=False, max_workers=0,
                 selected_wsi_paths=[str(SLIDES / n) for n in names])
t0 = time.time()
proc.run_segmentation_job(model, seg_mag=model.target_mag, holes_are_tissue=True,
                          artifact_remover_model=remover, batch_size=64, device=device)
meta = dict(arm=arm, segmenter=seg, device=device, convert=CONVERT, read_region_calls=_calls[0], profiles=sorted(set(_profiles)), seconds=time.time() - t0, torch=torch.__version__,
            openslide=openslide.__library_version__, python=platform.python_version(),
            trident_commit=os.popen(f'git -C {ROOT/"TRIDENT"} rev-parse HEAD').read().strip(), levels=levels)
(job / f'run_meta_{int(t0)}.json').write_text(json.dumps(meta, indent=1))
print(json.dumps({k: v for k, v in meta.items() if k != 'levels'}))
