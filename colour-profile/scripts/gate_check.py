"""Gate (PLAN.md): with conversion off, every region equals the original study's region (zero symmetric difference)."""
import json, sys
from pathlib import Path
import geopandas as gpd, shapely
ROOT = Path(__file__).resolve().parents[1]; ORIG = ROOT.parent / 'trident-plism' / 'out'
U = lambda p: shapely.union_all(gpd.read_file(p).geometry.values)
res = {}
for arm in ['otsu', 'grandqc']:
    files = sorted((ROOT / 'out' / f'gate_{arm}' / 'contours_geojson').glob('*.geojson'))
    d = {p.stem: U(p).symmetric_difference(U(ORIG / arm / 'contours_geojson' / p.name)).area for p in files}
    res[arm] = dict(scans=len(d), nonzero={k: v for k, v in d.items() if v != 0})
ok = all(r['scans'] == 26 and not r['nonzero'] for r in res.values())
(ROOT / 'results').mkdir(exist_ok=True)
(ROOT / 'results' / 'gate.json').write_text(json.dumps(dict(passed=ok, **res), indent=1))
print('GATE', 'PASS' if ok else 'FAIL', res)
sys.exit(0 if ok else 1)
