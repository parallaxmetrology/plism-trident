"""Score TRIDENT tissue regions on the 156 registered PLISM fields (PLAN readings 1-3 + secondary)."""
import json, csv, glob, statistics
from pathlib import Path
import numpy as np
import geopandas as gpd
from shapely.geometry import Polygon
from shapely.ops import unary_union

ROOT = Path(__file__).resolve().parents[1]
MAPS = Path('/Volumes/Temp_flex/parallax_pathology/HISTOQC_PAIRED_SELECTION_20261111/PLISM_01/maps')
ARMS = ['hest', 'grandqc', 'otsu', 'hest_artifacts']
SCANS = ['AT2', 'GT450']
OUT = ROOT / 'results'
OUT.mkdir(exist_ok=True)


def meta_for(arm):
    levels = {}
    for f in sorted((ROOT / 'out' / arm).glob('run_meta_*.json')):
        m = json.loads(f.read_text())
        levels.update(m['levels'])
    return levels


def region(arm, name):
    p = ROOT / 'out' / arm / 'contours_geojson' / f'{name}.geojson'
    if not p.exists():
        return None
    g = gpd.read_file(p)
    return unary_union(list(g.geometry)) if len(g) else Polygon()


fields, sections, scans = [], [], []
summary = {}
for arm in ARMS:
    lv = meta_for(arm)
    if not lv:
        continue
    complete = True
    arm_sections = []
    for mf in sorted(MAPS.glob('*.json')):
        sec = mf.stem
        rows = json.loads(mf.read_text())
        regs, areas = [], []
        for scan in SCANS:
            name = f'{sec}_{scan}'
            r = region(arm, name)
            if r is None:
                complete = False
                break
            m = lv[name + '.svs']
            mpp = m['mpp']
            area_mm2 = r.area * mpp ** 2 / 1e6
            # effective minimum piece size in mask_to_gdf: area > 1000 px of a mask resized to 2000 rows
            h0 = m['dims'][1]
            min_piece_mm2 = 1000 * (h0 * mpp / 2000) ** 2 / 1e6
            scans.append(dict(arm=arm, scan=name, mpp=mpp, level=m['level'], wanted_downsample=round(m['wanted_downsample'], 3),
                              custom_downsample=round(m['custom_downsample'], 3), pieces=len(getattr(r, 'geoms', [r])) if not r.is_empty else 0,
                              tissue_mm2=round(area_mm2, 4), min_piece_mm2=round(min_piece_mm2, 4)))
            regs.append(r)
            areas.append(area_mm2)
        if not complete:
            break
        counts = dict(both_in=0, AT2_only=0, GT450_only=0, both_out=0)
        for row in rows:
            frac = []
            for coords, r in zip(row['native_pixel_center_frame'], regs):
                poly = Polygon(np.array(coords, dtype=float) + 0.5)
                frac.append(poly.intersection(r).area / poly.area if not r.is_empty else 0.0)
            a, b = (int(f >= 0.5) for f in frac)
            key = ['both_out', 'GT450_only', 'AT2_only', 'both_in'][2 * a + b]
            counts[key] += 1
            fields.append(dict(arm=arm, section=sec, field=row['j'], prior_status=row['status'],
                               AT2_fraction=round(frac[0], 6), GT450_fraction=round(frac[1], 6),
                               AT2_in=a, GT450_in=b, switched=int(a != b)))
        ratio = areas[1] / areas[0] if areas[0] > 0 else float('nan')
        s = dict(arm=arm, section=sec, n=len(rows), **counts,
                 switch_fraction=(counts['AT2_only'] + counts['GT450_only']) / len(rows),
                 AT2_mm2=round(areas[0], 4), GT450_mm2=round(areas[1], 4), GT450_over_AT2=round(ratio, 4))
        arm_sections.append(s)
    if not complete or len(arm_sections) != 13:
        print(arm, 'incomplete:', len(arm_sections), 'sections')
        continue
    sections += arm_sections
    sw_a = sum(s['AT2_only'] for s in arm_sections)
    sw_b = sum(s['GT450_only'] for s in arm_sections)
    ratios = [s['GT450_over_AT2'] for s in arm_sections]
    summary[arm] = dict(fields=156, switched=sw_a + sw_b, AT2_only=sw_a, GT450_only=sw_b,
                        mean_section_switch_fraction=round(statistics.mean(s['switch_fraction'] for s in arm_sections), 4),
                        area_ratio_median=round(statistics.median(ratios), 4),
                        area_ratio_min=min(ratios), area_ratio_max=max(ratios),
                        GT450_smaller=sum(r < 1 for r in ratios),
                        near_empty=[s['section'] + ('_GT450' if s['GT450_over_AT2'] < 0.1 else '_AT2')
                                    for s in arm_sections if s['GT450_over_AT2'] < 0.1 or s['GT450_over_AT2'] > 10])

summary['context_histoqc_default'] = dict(switched=52, AT2_only=47, GT450_only=5, usable_ratio_median=0.065,
                                          source='parallaxmetrology/plism-histoqc v1.0.0 tables + component_sizes.csv')
for fn, rows in [('fields.csv', fields), ('sections.csv', sections), ('scans.csv', scans)]:
    if rows:
        with open(OUT / fn, 'w', newline='') as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0]))
            w.writeheader()
            w.writerows(rows)
(OUT / 'summary.json').write_text(json.dumps(summary, indent=1))
print(json.dumps(summary, indent=1))
