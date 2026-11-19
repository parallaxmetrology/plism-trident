"""Overlay figure for the artifact arm: HEST alone (grey) vs HEST + artifact removal (orange), both scanners."""
import openslide, geopandas as gpd, numpy as np
from PIL import Image, ImageDraw
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
secs = ['HR', 'MY', 'LM', 'KR']
W = 700; tiles = []
for s in secs:
    row = []
    for sc in ['AT2', 'GT450']:
        sl = openslide.OpenSlide(str(ROOT / f'data/slides/{s}_{sc}.svs'))
        th = sl.get_thumbnail((W, W)).convert('RGB'); f = th.size[0] / sl.dimensions[0]
        d = ImageDraw.Draw(th)
        for arm, col, wd in [('hest', (120, 120, 120), 3), ('hest_artifacts', (235, 104, 52), 2)]:
            for g in gpd.read_file(ROOT / f'out/{arm}/contours_geojson/{s}_{sc}.geojson').geometry.explode(index_parts=False):
                for ring in [g.exterior, *g.interiors]:
                    d.line([(x * f, y * f) for x, y in ring.coords], fill=col, width=wd)
        d.rectangle([0, 0, 150, 28], fill='white'); d.text((6, 6), f'{s} {sc}', fill='black')
        row.append(th)
    tiles.append(row)
h = max(t.size[1] for r in tiles for t in r)
out = Image.new('RGB', (2 * W + 10, len(secs) * (h + 10)), 'white')
for i, r in enumerate(tiles):
    for j, t in enumerate(r): out.paste(t, (j * (W + 10), i * (h + 10)))
out.save(ROOT / 'figs/check_artifacts_HR_MY_LM_KR.jpg', quality=85)
