"""Second-pass checks (19 Nov 2026): source integrity, brightness, coordinate frames, independent re-scoring.
Writes results/checks.json and results/brightness.csv."""
import json, glob, csv, hashlib, os
import numpy as np, tifffile, openslide, geopandas as gpd, shapely
from shapely.prepared import prep
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = '/Volumes/Temp_flex/parallax_pathology/HISTOQC_PAIRED_SELECTION_20261111/PLISM_01/'
out = {}

# 1. AT2 range-acquired copies: every tile of every reduced level inside fetched ranges; fetched ranges match receipt hashes
integ = {}
for f in sorted(glob.glob(SRC + 'sources/*_AT2.svs')):
    rec = json.load(open(f + '.ranges.json'))
    M = []
    for a, b in sorted((a, b) for a, b, *_ in rec['blocks']):
        if M and a <= M[-1][1]: M[-1][1] = max(M[-1][1], b)
        else: M.append([a, b])
    cov = lambda o, n: any(a <= o and o + n <= b for a, b in M)
    uncovered = 0; tiles = 0
    with tifffile.TiffFile(f) as t:
        for k, p in enumerate(t.pages):
            if k == 0: continue
            for o, n in zip(p.dataoffsets, p.databytecounts):
                tiles += 1; uncovered += (n > 0 and not cov(o, n))
    bad = 0
    with open(f, 'rb') as fh:
        for a, b, h in rec['blocks']:
            fh.seek(a); bad += hashlib.sha256(fh.read(b - a)).hexdigest() != h
    integ[os.path.basename(f)] = dict(reduced_level_tiles=tiles, tiles_outside_fetched=uncovered, blocks=len(rec['blocks']), hash_mismatches=bad)
out['at2_source_integrity'] = integ

# 2. Tissue brightness per scan (2000-px thumbnail; tissue = luma below 95th percentile minus 25)
rows = []
for f in sorted(glob.glob(str(ROOT / 'data/slides/*.svs'))):
    im = np.asarray(openslide.OpenSlide(f).get_thumbnail((2000, 2000)).convert('RGB')).astype(float)
    L = 0.299 * im[..., 0] + 0.587 * im[..., 1] + 0.114 * im[..., 2]
    t = L < np.percentile(L, 95) - 25
    rows.append(dict(scan=Path(f).stem, background_luma=round(float(np.percentile(L, 95)), 1), tissue_median_luma=round(float(np.median(L[t])), 1)))
with open(ROOT / 'results/brightness.csv', 'w', newline='') as fh:
    w = csv.DictWriter(fh, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)

# 3. Field map order and 4. independent re-scoring by 40x40 point sampling
lv = {}
for f in glob.glob(str(ROOT / 'out/*/run_meta_*.json')):
    m = json.load(open(f)); lv.update({(m['arm'], k[:-4]): v for k, v in m['levels'].items()})
mine = {(r['arm'], r['section'], r['field']): r for r in csv.DictReader(open(ROOT / 'results/fields.csv'))}
u = np.linspace(0.0125, 0.9875, 40); UU, VV = np.meshgrid(u, u)
side = []
rescore = {}
for arm in ['hest', 'grandqc', 'otsu', 'hest_artifacts']:
    if not (ROOT / 'out' / arm / 'contours_geojson').exists() or len(list((ROOT / 'out' / arm / 'contours_geojson').glob('*.geojson'))) < 26:
        continue
    sw = 0; dec_mis = 0; frac_mis = 0
    for mf in sorted(glob.glob(SRC + 'maps/*.json')):
        sec = Path(mf).stem; fields = json.load(open(mf))
        geo = {sc: prep(shapely.union_all(gpd.read_file(ROOT / f'out/{arm}/contours_geojson/{sec}_{sc}.geojson').geometry.values)) for sc in ['AT2', 'GT450']}
        for r in fields:
            fr = []
            for k, sc in enumerate(['AT2', 'GT450']):
                c = np.array(r['native_pixel_center_frame'][k]) + 0.5
                if arm == 'hest' and sec == 'GIV' and r['j'] == 0:
                    side.append(round(float(np.linalg.norm(c[1] - c[0])) * lv[(arm, f'{sec}_{sc}')]['mpp'], 2))
                P = ((1-UU)*(1-VV))[..., None]*c[0] + (UU*(1-VV))[..., None]*c[1] + (UU*VV)[..., None]*c[2] + ((1-UU)*VV)[..., None]*c[3]
                fr.append(float(np.mean([geo[sc].contains(p) for p in shapely.points(P.reshape(-1, 2))])))
            a, b = (int(x >= 0.5) for x in fr); sw += a != b
            m = mine[(arm, sec, str(r['j']))]
            dec_mis += (a, b) != (int(m['AT2_in']), int(m['GT450_in']))
            frac_mis += abs(fr[0] - float(m['AT2_fraction'])) > 0.03 or abs(fr[1] - float(m['GT450_fraction'])) > 0.03
    rescore[arm] = dict(switched=sw, decision_mismatches=dec_mis, fraction_mismatches_over_0_03=frac_mis)
out['field_side_um_AT2_then_GT450'] = side
out['independent_rescore_point_sampling'] = rescore

# 5. HistoQC context recount from the earlier study's own table
h = list(csv.DictReader(open(SRC + 'field_results.csv')))
d = [x for x in h if x['discordant'] == 'True']
out['histoqc_context_recount'] = dict(fields=len(h), switched=len(d), AT2_only=sum(x['AT2_in'] == '1' for x in d), GT450_only=sum(x['GT450_in'] == '1' for x in d))

(ROOT / 'results/checks.json').write_text(json.dumps(out, indent=1))
print(json.dumps({k: v for k, v in out.items() if k != 'at2_source_integrity'}, indent=1))
print('integrity:', sum(v['tiles_outside_fetched'] for v in integ.values()), 'tiles outside;', sum(v['hash_mismatches'] for v in integ.values()), 'hash mismatches;', sum(v['blocks'] for v in integ.values()), 'blocks')
