"""Repeatability of the artifact arm: compare out/hest_artifacts_repeat with out/hest_artifacts on the same scans.
Writes results/artifact_repeat.json."""
import json, glob
import numpy as np, geopandas as gpd, shapely
from shapely.geometry import Polygon
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
SRC = '/Volumes/Temp_flex/parallax_pathology/HISTOQC_PAIRED_SELECTION_20261111/PLISM_01/'
rep = sorted((ROOT / 'out/hest_artifacts_repeat/contours_geojson').glob('*.geojson'))
meta = {}
for f in glob.glob(str(ROOT / 'out/*/run_meta_*.json')):
    m = json.load(open(f)); meta.update({(m['arm'], k[:-4]): v['mpp'] for k, v in m['levels'].items()})
U = lambda arm, n: shapely.union_all(gpd.read_file(ROOT / f'out/{arm}/contours_geojson/{n}.geojson').geometry.values)
out = {}
for p in rep:
    n = p.stem; sec, sc = n.rsplit('_', 1); k = {'AT2': 0, 'GT450': 1}[sc]
    a, b = U('hest_artifacts', n), U('hest_artifacts_repeat', n)
    s2 = (meta[('hest_artifacts', n)] / 1000) ** 2
    fields = json.load(open(SRC + f'maps/{sec}.json'))
    fa, fb = [], []
    for r in fields:
        poly = Polygon(np.array(r['native_pixel_center_frame'][k]) + 0.5)
        fa.append(a.intersection(poly).area / poly.area); fb.append(b.intersection(poly).area / poly.area)
    out[n] = dict(first_mm2=round(a.area * s2, 4), repeat_mm2=round(b.area * s2, 4),
                  symmetric_difference_mm2=round(a.symmetric_difference(b).area * s2, 4),
                  field_decision_changes=int(sum((x >= 0.5) != (y >= 0.5) for x, y in zip(fa, fb))),
                  max_field_fraction_change=round(float(max(abs(x - y) for x, y in zip(fa, fb))), 4))
(ROOT / 'results/artifact_repeat.json').write_text(json.dumps(out, indent=1))
print(json.dumps(out, indent=1))
