"""Recompute every field decision, section area and summary count from the stored TRIDENT regions.

    python3 reproduce.py

Needs Python 3.10+, numpy and shapely 2. No slides or TRIDENT install needed. Reads regions/, fields/ and
run_meta/, recomputes results/fields.csv, sections.csv and the switch counts in summary.json and
artifact_repeat.json, and reports any difference from the shipped tables. Since v1.1.0 it does the same for the
colour-profile rerun in colour-profile/, including its gate. Exit code 0 means all match.
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


def mpp_table(arm, base=ROOT):
    out = {}
    for f in sorted((base / 'run_meta' / arm).glob('run_meta_*.json')):
        out.update({k[:-4]: v['mpp'] for k, v in json.loads(f.read_text())['levels'].items()})
    return out


def region(arm, scan, base=ROOT):
    gj = json.loads(gzip.decompress((base / 'regions' / arm / f'{scan}.geojson.gz').read_bytes()))
    geoms = [shape(f['geometry']) for f in gj['features']]
    return shapely.union_all(geoms) if geoms else Polygon()


def fractions(regs, row):
    out = []
    for coords, r in zip(row['native_pixel_center_frame'], regs):
        poly = Polygon(np.array(coords, dtype=float) + 0.5)  # pixel centres to pixel edges
        out.append(poly.intersection(r).area / poly.area if not r.is_empty else 0.0)
    return out


def score(arms, base):
    """Recompute field decisions, section areas and switch counts for arms stored under base; compare with base/results."""
    shipped_fields = {(r['arm'], r['section'], r['field']): r for r in csv.DictReader(open(base / 'results/fields.csv'))}
    shipped_sections = {(r['arm'], r['section']): r for r in csv.DictReader(open(base / 'results/sections.csv'))}
    summary = json.loads((base / 'results/summary.json').read_text())
    areas = {}
    for arm in arms:
        mpp = mpp_table(arm, base)
        switched = at2_only = gt450_only = 0
        for mf in sorted((ROOT / 'fields').glob('*.json')):
            sec = mf.stem
            regs = [region(arm, f'{sec}_{s}', base) for s in SCANS]
            for s, r in zip(SCANS, regs):
                area = r.area * mpp[f'{sec}_{s}'] ** 2 / 1e6
                areas[(arm, sec, s)] = area
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
        print(f'{arm:18s} {switched:3d} of 156 fields switch ({at2_only} AT2-only, {gt450_only} GT450-only)')
    return areas


areas = score(ARMS, ROOT)

# Repeat runs: identical regions
for first, again, label in [('hest', 'hest_repeat', 'HEST repeat'), ('hest_artifacts', 'hest_artifacts_repeat', 'artifact repeat')]:
    for p in sorted((ROOT / 'regions' / again).glob('*.geojson.gz')):
        scan = p.name[:-len('.geojson.gz')]
        d = region(first, scan).symmetric_difference(region(again, scan)).area
        check(d == 0, f'{label} {scan}: symmetric difference {d} px²')
        print(f'{label:15s} {scan:9s} symmetric difference from first run: {d:g} px²')

# Colour-profile rerun (added 25 November 2026; see colour-profile/README.md)
CP = ROOT / 'colour-profile'
want = (CP / 'PLAN.sha256').read_text().split()[0]
check(want == hashlib.sha256((CP / 'PLAN.md').read_bytes()).hexdigest(), 'colour-profile/PLAN.md hash differs from its PLAN.sha256')
# Gate: wrapper on, conversion off, regions identical to the original arms
for arm in ['otsu', 'grandqc']:
    scans = sorted(p.name[:-len('.geojson.gz')] for p in (CP / 'regions' / f'gate_{arm}').glob('*.geojson.gz'))
    nonzero = [sc for sc in scans if region(arm, sc).symmetric_difference(region(f'gate_{arm}', sc, CP)).area != 0]
    check(len(scans) == 26 and not nonzero, f'gate_{arm}: {len(scans)} scans, differing: {nonzero}')
    print(f'gate_{arm:13s} {len(scans)} scans, {len(nonzero)} differ from the original regions')
cp_areas = score(['icc_otsu', 'icc_grandqc', 'icc_hest', 'icc_hest_artifacts'], CP)
# Artifact step: share of HEST's region kept, pooled over sections, without and with the profiles
secs = sorted(mf.stem for mf in (ROOT / 'fields').glob('*.json'))
for label, A, h, ha in [('default read', areas, 'hest', 'hest_artifacts'), ('profile applied', cp_areas, 'icc_hest', 'icc_hest_artifacts')]:
    kept = {s: sum(A[(ha, x, s)] for x in secs) / sum(A[(h, x, s)] for x in secs) for s in SCANS}
    print(f'artifact step, {label:15s} keeps {kept["AT2"]:.0%} of HEST AT2 tissue, {kept["GT450"]:.0%} of GT450')
lower = sum(cp_areas[('icc_hest_artifacts', x, 'AT2')] / cp_areas[('icc_hest', x, 'AT2')] <
            areas[('hest_artifacts', x, 'AT2')] / areas[('hest', x, 'AT2')] for x in secs)
print(f'artifact step keeps a smaller share of AT2 tissue with the profile applied on {lower} of {len(secs)} sections')

print('\nALL MATCH' if not problems else '\n' + '\n'.join(problems))
sys.exit(1 if problems else 0)
