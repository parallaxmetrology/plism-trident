"""Recompute every field decision, section area and summary count from the stored TRIDENT regions.

    python3 reproduce.py

Needs Python 3.10+, numpy and shapely 2. No slides or TRIDENT install needed. Reads regions/, fields/ and
run_meta/, recomputes results/fields.csv, sections.csv and the switch counts in summary.json and
artifact_repeat.json, and reports any difference from the shipped tables. Exit code 0 means all match.
"""
import csv, gzip, hashlib, json, sys
from pathlib import Path
import numpy as np
import shapely
from shapely.geometry import Polygon, shape

ROOT = Path(__file__).resolve().parent
ARMS = ['hest', 'grandqc', 'otsu', 'hest_artifacts']
SCANS = ['AT2', 'GT450']
problems = []


def check(ok, msg):
    if not ok:
        problems.append(msg)


# 0. Frozen plan and addenda match their recorded SHA-256
for name in ['PLAN', 'ADDENDUM_1', 'ADDENDUM_2', 'ADDENDUM_3']:
    want = (ROOT / f'{name}.sha256').read_text().split()[0]
    got = hashlib.sha256((ROOT / f'{name}.md').read_bytes()).hexdigest()
    check(want == got, f'{name}.md hash differs from {name}.sha256')


def mpp_table(arm):
    out = {}
    for f in sorted((ROOT / 'run_meta' / arm).glob('run_meta_*.json')):
        out.update({k[:-4]: v['mpp'] for k, v in json.loads(f.read_text())['levels'].items()})
    return out


def region(arm, scan):
    gj = json.loads(gzip.decompress((ROOT / 'regions' / arm / f'{scan}.geojson.gz').read_bytes()))
    geoms = [shape(f['geometry']) for f in gj['features']]
    return shapely.union_all(geoms) if geoms else Polygon()


def fractions(regs, row):
    out = []
    for coords, r in zip(row['native_pixel_center_frame'], regs):
        poly = Polygon(np.array(coords, dtype=float) + 0.5)  # pixel centres to pixel edges
        out.append(poly.intersection(r).area / poly.area if not r.is_empty else 0.0)
    return out


shipped_fields = {(r['arm'], r['section'], r['field']): r for r in csv.DictReader(open(ROOT / 'results/fields.csv'))}
shipped_sections = {(r['arm'], r['section']): r for r in csv.DictReader(open(ROOT / 'results/sections.csv'))}
summary = json.loads((ROOT / 'results/summary.json').read_text())

for arm in ARMS:
    mpp = mpp_table(arm)
    switched = at2_only = gt450_only = 0
    for mf in sorted((ROOT / 'fields').glob('*.json')):
        sec = mf.stem
        regs = [region(arm, f'{sec}_{s}') for s in SCANS]
        for s, r in zip(SCANS, regs):
            area = r.area * mpp[f'{sec}_{s}'] ** 2 / 1e6
            ref = float(shipped_sections[(arm, sec)][f'{s}_mm2'])
            check(abs(area - ref) < 1e-3, f'{arm} {sec} {s}: area {area:.4f} vs shipped {ref}')
        for row in json.loads(mf.read_text()):
            fa, fb = fractions(regs, row)
            a, b = int(fa >= 0.5), int(fb >= 0.5)
            ref = shipped_fields[(arm, sec, str(row['j']))]
            check((a, b) == (int(ref['AT2_in']), int(ref['GT450_in'])), f'{arm} {sec} field {row["j"]}: decision differs')
            check(abs(fa - float(ref['AT2_fraction'])) < 1e-5 and abs(fb - float(ref['GT450_fraction'])) < 1e-5,
                  f'{arm} {sec} field {row["j"]}: fraction differs')
            switched += a != b; at2_only += a > b; gt450_only += b > a
    s = summary[arm]
    check((switched, at2_only, gt450_only) == (s['switched'], s['AT2_only'], s['GT450_only']),
          f'{arm}: {switched} switched ({at2_only}/{gt450_only}) vs shipped {s["switched"]} ({s["AT2_only"]}/{s["GT450_only"]})')
    print(f'{arm:15s} {switched:3d} of 156 fields switch ({at2_only} AT2-only, {gt450_only} GT450-only)')

# Repeat runs: identical regions
for first, again, label in [('hest', 'hest_repeat', 'HEST repeat'), ('hest_artifacts', 'hest_artifacts_repeat', 'artifact repeat')]:
    for p in sorted((ROOT / 'regions' / again).glob('*.geojson.gz')):
        scan = p.name[:-len('.geojson.gz')]
        d = region(first, scan).symmetric_difference(region(again, scan)).area
        check(d == 0, f'{label} {scan}: symmetric difference {d} px²')
        print(f'{label:15s} {scan:9s} symmetric difference from first run: {d:g} px²')

print('\nALL MATCH' if not problems else '\n' + '\n'.join(problems))
sys.exit(1 if problems else 0)
