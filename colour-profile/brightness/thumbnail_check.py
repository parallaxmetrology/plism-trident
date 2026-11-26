"""Prior look (disclosed in PLAN.md): median tissue luma on 2000-px thumbnails, without and with the embedded profile."""
import glob, json, os, statistics as st
import numpy as np, openslide
from PIL import ImageCms
SRC = '/Volumes/Temp_flex/parallax_pathology/HISTOQC_PAIRED_SELECTION_20261111/PLISM_01/sources/'
srgb = ImageCms.createProfile('sRGB'); L = lambda a: 0.299 * a[..., 0] + 0.587 * a[..., 1] + 0.114 * a[..., 2]
res = {}
for f in sorted(glob.glob(SRC + '*.svs')):
    s = openslide.OpenSlide(f); im = s.get_thumbnail((2000, 2000)).convert('RGB')
    im2 = ImageCms.applyTransform(im, ImageCms.buildTransform(s.color_profile, srgb, 'RGB', 'RGB', renderingIntent=0))
    a, b = L(np.asarray(im).astype(float)), L(np.asarray(im2).astype(float))
    t = a < np.percentile(a, 95) - 25
    res[os.path.basename(f)[:-4]] = (float(np.median(a[t])), float(np.median(b[t])))
out = {}
for sec in sorted({k.rsplit('_', 1)[0] for k in res}):
    A, G = res[sec + '_AT2'], res[sec + '_GT450']
    out[sec] = dict(raw=[round(A[0], 1), round(G[0], 1)], icc=[round(A[1], 1), round(G[1], 1)])
secs = [k for k in out]
out['_median_gap_raw'] = round(st.median(abs(res[s + '_AT2'][0] - res[s + '_GT450'][0]) for s in secs), 2)
out['_median_gap_icc'] = round(st.median(abs(res[s + '_AT2'][1] - res[s + '_GT450'][1]) for s in secs), 2)
out['_icc_AT2_brighter'] = sum(out[s]['icc'][0] > out[s]['icc'][1] for s in secs)
open('thumbnail_check.json', 'w').write(json.dumps(out, indent=1))
print(out['_median_gap_raw'], out['_median_gap_icc'], out['_icc_AT2_brighter'], out['HR'])
