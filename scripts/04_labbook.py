"""Build LABBOOK.html (self-contained) from results/*.csv, summary.json, run_meta files and figs/."""
import json, csv, base64, math, html, glob
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
R = ROOT / 'results'
S = json.loads((R / 'summary.json').read_text())
sections = list(csv.DictReader(open(R / 'sections.csv')))
fields = list(csv.DictReader(open(R / 'fields.csv')))
scans = list(csv.DictReader(open(R / 'scans.csv')))
ARMS = [a for a in ['hest', 'grandqc', 'otsu'] if a in S]
LABEL = {'hest': 'HEST (default)', 'grandqc': 'GrandQC', 'otsu': 'Otsu', 'hest_artifacts': 'HEST + remove_artifacts'}
COL = {'hest': 'var(--s1)', 'grandqc': 'var(--s2)', 'otsu': 'var(--s3)'}
sha = lambda f: (ROOT / f).read_text().split()[0] if (ROOT / f).exists() else 'missing'
esc = html.escape
CK = json.loads((R / 'checks.json').read_text())
tiles_out = sum(v['tiles_outside_fetched'] for v in CK['at2_source_integrity'].values())
hash_bad = sum(v['hash_mismatches'] for v in CK['at2_source_integrity'].values())
BR = {r['scan']: float(r['tissue_median_luma']) for r in csv.DictReader(open(R / 'brightness.csv'))}
br_other = lambda sc: sorted(v for k, v in BR.items() if k.endswith('_' + sc) and not k.startswith('HR_'))


def runs():
    out = []
    for f in sorted(glob.glob(str(ROOT / 'out' / '*' / 'run_meta_*.json'))):
        m = json.loads(Path(f).read_text())
        if m['arm'].startswith('smoke'):
            continue
        sc = sorted({k.rsplit('_', 1)[1][:-4] for k in m['levels']})
        lv = sorted({(k.rsplit('_', 1)[1][:-4], v['level'], round(v['custom_downsample'], 3)) for k, v in m['levels'].items()})
        out.append(dict(arm=m['arm'], seg=m['segmenter'], device=m['device'], n=len(m['levels']), scanners='+'.join(sc),
                        seconds=round(m['seconds']), levels='; '.join(f'{s}: level {l}, extra downsample {d}' for s, l, d in lv),
                        art='; '.join(sorted({f"{k.rsplit('_',1)[1][:-4]}: level {v['artifact_level']}" for k, v in m['levels'].items() if 'artifact_level' in v}))))
    return out


def img(p, alt, w='100%'):
    b = base64.b64encode((ROOT / p).read_bytes()).decode()
    return f'<img src="data:image/jpeg;base64,{b}" alt="{esc(alt)}" style="width:{w};max-width:100%;height:auto;border-radius:6px">'


def table(rows, cols, heads=None, num=()):
    h = ''.join(f'<th class="{"n" if c in num else ""}">{esc(x)}</th>' for c, x in zip(cols, heads or cols))
    b = ''.join('<tr>' + ''.join(f'<td class="{"n" if c in num else ""}">{esc(str(r[c]))}</td>' for c in cols) + '</tr>' for r in rows)
    return f'<div class="tw"><table><thead><tr>{h}</tr></thead><tbody>{b}</tbody></table></div>'


# --- chart 1: switched fields per tool (bars), HistoQC context in grey
def chart_switch():
    items = [(LABEL[a], S[a]['switched'], COL[a]) for a in ARMS] + [('HistoQC default (earlier study)', S['context_histoqc_default']['switched'], 'var(--muted)')]
    W, rowh, lab, maxv = 640, 34, 230, 156
    H = rowh * len(items) + 34
    sx = lambda v: lab + (W - lab - 60) * v / maxv
    g = []
    for t in [0, 39, 78, 117, 156]:
        g.append(f'<line x1="{sx(t)}" x2="{sx(t)}" y1="6" y2="{H-24}" class="grid"/><text x="{sx(t)}" y="{H-8}" class="tick" text-anchor="middle">{t}</text>')
    for i, (name, v, c) in enumerate(items):
        y = 10 + i * rowh
        w = max(sx(v) - lab, 2)
        g.append(f'<g class="hov"><title>{esc(name)}: {v} of 156 fields switched</title>'
                 f'<rect x="{lab}" y="{y}" width="{w}" height="20" rx="4" fill="{c}"/>'
                 f'<text x="{lab-8}" y="{y+14}" text-anchor="end" class="lab">{esc(name)}</text>'
                 f'<text x="{lab+w+6}" y="{y+14}" class="val">{v}</text></g>')
    return f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="Fields switched per tool">{"".join(g)}</svg>'


# --- chart 2: per-section GT450/AT2 area ratio, log x
def chart_ratio():
    secs = [s['section'] for s in sections if s['arm'] == ARMS[0]]
    W, lab, rowh = 640, 60, 24
    H = rowh * len(secs) + 50
    lo, hi = math.log(0.5), math.log(10)
    sx = lambda v: lab + (W - lab - 20) * (math.log(v) - lo) / (hi - lo)
    g = []
    for t in [0.5, 0.75, 1, 1.5, 2, 5, 10]:
        cls = 'axis' if t == 1 else 'grid'
        g.append(f'<line x1="{sx(t):.1f}" x2="{sx(t):.1f}" y1="4" y2="{H-30}" class="{cls}"/><text x="{sx(t):.1f}" y="{H-14}" class="tick" text-anchor="middle">{t}</text>')
    off = {a: (i - 1) * 6 for i, a in enumerate(ARMS)}
    for j, sec in enumerate(secs):
        y = 14 + j * rowh
        g.append(f'<text x="{lab-8}" y="{y+4}" text-anchor="end" class="lab">{sec}</text>')
        for a in ARMS:
            r = next(s for s in sections if s['arm'] == a and s['section'] == sec)
            v = float(r['GT450_over_AT2'])
            g.append(f'<g class="hov"><title>{sec}, {LABEL[a]}: GT450/AT2 = {v} (AT2 {r["AT2_mm2"]} mm², GT450 {r["GT450_mm2"]} mm²)</title>'
                     f'<circle cx="{sx(v):.1f}" cy="{y+off[a]}" r="5" fill="{COL[a]}" stroke="var(--bg)" stroke-width="2"/>'
                     f'<circle cx="{sx(v):.1f}" cy="{y+off[a]}" r="11" fill="transparent"/></g>')
    g.append(f'<text x="{(W+lab)/2}" y="{H-1}" class="tick" text-anchor="middle">GT450 tissue area / AT2 tissue area (log scale; 1 = same)</text>')
    return f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="Area ratio per section">{"".join(g)}</svg>'


legend = '<div class="legend">' + ''.join(f'<span><i style="background:{COL[a]}"></i>{LABEL[a]}</span>' for a in ARMS) + '</div>'

summ_rows = []
for a in ARMS + (['hest_artifacts'] if 'hest_artifacts' in S else []):
    s = S[a]
    summ_rows.append(dict(tool=LABEL[a], sw=f"{s['switched']} of 156", split=f"{s['AT2_only']} / {s['GT450_only']}",
                          msf=f"{s['mean_section_switch_fraction']:.3f}", med=f"{s['area_ratio_median']:.3f}",
                          rng=f"{s['area_ratio_min']:.3f} to {s['area_ratio_max']:.3f}", sm=f"{s['GT450_smaller']} of 13",
                          ne=', '.join(s['near_empty']) or 'none'))
c = S['context_histoqc_default']
summ_rows.append(dict(tool='HistoQC default (context, different rule)', sw=f"{c['switched']} of 156", split=f"{c['AT2_only']} / {c['GT450_only']}",
                      msf='n/a', med=f"{c['usable_ratio_median']} (usable tissue)", rng='n/a', sm='n/a', ne='n/a'))

sw_rows = [dict(tool=LABEL[f['arm']], section=f['section'], field=f['field'], a=f['AT2_fraction'], b=f['GT450_fraction'],
                side='AT2 only' if f['AT2_in'] == '1' else 'GT450 only') for f in fields if f['switched'] == '1' and f['arm'] in ('hest', 'grandqc', 'hest_artifacts')]
otsu_sw = [f for f in fields if f['switched'] == '1' and f['arm'] == 'otsu']
otsu_whole = sum(1 for f in otsu_sw if min(float(f['AT2_fraction']), float(f['GT450_fraction'])) < 0.05 and max(float(f['AT2_fraction']), float(f['GT450_fraction'])) > 0.95)
whole = lambda arm: sum(1 for f in fields if f['arm'] == arm and f['switched'] == '1' and min(float(f['AT2_fraction']), float(f['GT450_fraction'])) < 0.05 and max(float(f['AT2_fraction']), float(f['GT450_fraction'])) > 0.95)

sec_rows = []
for s in sections:
    sec_rows.append(dict(tool=LABEL[s['arm']], section=s['section'], n=s['n'], both_in=s['both_in'], a=s['AT2_only'], b=s['GT450_only'],
                         out=s['both_out'], A=s['AT2_mm2'], B=s['GT450_mm2'], r=s['GT450_over_AT2']))

hest_scans = [r for r in scans if r['arm'] == 'hest']
mp = lambda sc: sorted(float(r['min_piece_mm2']) for r in hest_scans if r['scan'].endswith(sc))
med = lambda v: (v[len(v) // 2] if len(v) % 2 else (v[len(v) // 2 - 1] + v[len(v) // 2]) / 2)
mpA, mpB = mp('_AT2'), mp('_GT450')

rp = json.loads(next((ROOT / 'out' / 'hest_repeat').glob('run_meta_*.json')).read_text())
art_status = ('complete; numbers in the summary table and switched-field list' if 'hest_artifacts' in S else
              'not complete when this lab book was built')

HR = {a: next(s for s in sections if s['arm'] == a and s['section'] == 'HR') for a in ARMS}
art_block = ''
AR = json.loads((ROOT / 'results/artifact_repeat.json').read_text()) if (ROOT / 'results/artifact_repeat.json').exists() else {}
if 'hest_artifacts' in S:
    SA = {(x['arm'], x['section']): x for x in sections}
    kept = [dict(section=sec, a=f"{float(SA[('hest_artifacts', sec)]['AT2_mm2']) / float(SA[('hest', sec)]['AT2_mm2']):.3f}",
                 b=f"{float(SA[('hest_artifacts', sec)]['GT450_mm2']) / float(SA[('hest', sec)]['GT450_mm2']):.3f}",
                 sw=f"{SA[('hest', sec)]['AT2_only']}+{SA[('hest', sec)]['GT450_only']} → {SA[('hest_artifacts', sec)]['AT2_only']}+{SA[('hest_artifacts', sec)]['GT450_only']}")
            for sec in sorted({x['section'] for x in sections})]
    nsec = sum(1 for x in sections if x['arm'] == 'hest_artifacts' and (int(x['AT2_only']) + int(x['GT450_only'])) > 0)
    HA = SA[('hest_artifacts', 'HR')]
    art_block = f"""<p>With artifact removal, {S['hest_artifacts']['switched']} fields switch ({S['hest_artifacts']['AT2_only']} AT2-only, {S['hest_artifacts']['GT450_only']} GT450-only), in {nsec} of 13 sections, against {S['hest']['switched']} for HEST alone; {whole('hest_artifacts')} are of the whole-core kind. The independent point-sampling rescore reproduces all {S['hest_artifacts']['switched']} (0 decision mismatches). The table gives the share of HEST's own region that remains after artifact removal, per scan, and the switched fields before and after (AT2-only + GT450-only). In HR the step keeps {float(HA['AT2_mm2']):.1f} mm² on AT2 and {float(HA['GT450_mm2']):.1f} mm² on GT450, of HEST's {float(HR['hest']['AT2_mm2']):.1f} and {float(HR['hest']['GT450_mm2']):.1f}; {HA['both_out']} of HR's 12 fields are outside the region on both scans. On the overlays the removed areas have straight, stepped edges in all four sections drawn, and their outline differs between the two scans of the same glass. Two GT450 scans (GMH, KRH) end slightly larger than HEST alone (ratio above 1); this was not investigated. Repeatability: HR and MY were run through the artifact arm a second time on both scanners (<code>scripts/07_artifact_repeat.py</code>, <code>results/artifact_repeat.json</code>); {', '.join(f"{k} {v['symmetric_difference_mm2']} mm²" for k, v in AR.items())} symmetric difference from the first run, and {sum(v['field_decision_changes'] for v in AR.values())} field decisions change. The differences between scanners are not run-to-run variation on these scans. A maintainer has described this model as removing even slightly out-of-focus regions (mahmoodlab/TRIDENT#202); no focus measurement was made here.</p>
{table(kept, ['section', 'a', 'b', 'sw'], ['section', 'kept after artifact removal, AT2', 'kept, GT450', 'switched: HEST → with artifact removal'], num=('a', 'b'))}
<figure>{img('figs/check_artifacts_HR_MY_LM_KR.jpg', 'HEST contours with and without artifact removal')}<figcaption>Grey: HEST alone. Orange: HEST followed by artifact removal. Rows: HR, MY, LM, KR; left AT2, right GT450. Drawn by <code>scripts/06_artifact_fig.py</code> from TRIDENT's <code>contours_geojson</code>.</figcaption></figure>"""

body = f"""
<header>
<p class="kicker">Lab book · Parallax Metrology · built from results/ by scripts/04_labbook.py</p>
<h1>Same tissue, two scanners: TRIDENT tissue segmentation on paired PLISM scans</h1>
<p class="lede">13 PLISM tissue-array sections, each scanned on Aperio AT2 and Aperio GT450, were run through TRIDENT's three tissue segmenters at their defaults. The tissue is fixed; only the scanner changes. This records how much each segmenter's tissue region changes, using the same 156 registered fields and admission rule as the earlier HistoQC study.</p>
</header>

<section><h2>1. Status and record</h2>
<ul>
<li>Plan written and frozen before any TRIDENT segmentation of these scans: <code>PLAN.md</code>, SHA-256 <code>{sha('PLAN.sha256')}</code>.</li>
<li>Addendum 1 (<code>{sha('ADDENDUM_1.sha256')[:12]}…</code>): at 10x TRIDENT reads level 0 of the GT450 files, so complete GT450 files were downloaded from figshare and MD5-checked; AT2 runs use the existing range-acquired copies, which are only ever read at reduced levels.</li>
<li>Addendum 2 (<code>{sha('ADDENDUM_2.sha256')[:12]}…</code>): data-loader workers set to 0 after a macOS fork crash; weights pinned locally with SHA-256.</li>
<li>Addendum 3 (<code>{sha('ADDENDUM_3.sha256')[:12]}…</code>): the artifact-removal step ignores the requested device (see section 7); for that secondary arm only, the device default is patched at run time. TRIDENT source is not edited.</li>
<li>Secondary arm <code>hest_artifacts</code>: {art_status}.</li>
<li>Posted 19 November 2026: the study as mahmoodlab/TRIDENT#250 (<code>ISSUE_DRAFT.md</code>) and a comment on #237 (<code>ISSUE_DRAFT_DEVICE.md</code>).</li>
</ul></section>

<section><h2>2. Material and software</h2>
<ul>
<li>26 scans: 13 H&amp;E sections from the PLISM dataset (Ochi et al., CC BY 4.0), each on AT2 (0.2532 µm/px) and GT450 (0.2621 µm/px). 156 registered 128 µm fields, 12 per section, with native level-0 polygons for both scanners, reused unchanged from the HistoQC study.</li>
<li>TRIDENT at commit <code>{rp['trident_commit']}</code>, torch {rp['torch']}, OpenSlide {rp['openslide']}, Python {rp['python']}. Segmenters at the defaults <code>run_batch_of_slides.py --task seg</code> uses: HEST (DeepLabV3, 10x), GrandQC (UNet++, 1x), Otsu (1.25x); confidence 0.5; holes counted as tissue; batch 64. HEST and GrandQC ran on Apple MPS, Otsu on CPU; one device per segmenter for all 26 scans.</li>
<li>Tissue region = union of polygons in TRIDENT's <code>contours_geojson</code>. A field is admitted on a scanner when at least half its area lies inside the region (exact polygon intersection). This rule is ours, not TRIDENT's.</li>
</ul></section>

<section><h2>3. Technical gate</h2>
<p>Every run's pyramid level, as chosen by TRIDENT's own rule (<code>get_best_level_and_custom_downsample</code>, tolerance 0.1), was recorded before segmenting. The runner stops if a range-acquired AT2 copy would be read at level 0; no run stopped.</p>
<p><b>Source integrity (second pass, <code>scripts/05_checks.py</code>):</b> in all 13 AT2 copies, every tile of every reduced-resolution page ({sum(v['reduced_level_tiles'] for v in CK['at2_source_integrity'].values())} tiles) lies inside the byte ranges actually fetched ({tiles_out} outside), and all {sum(v['blocks'] for v in CK['at2_source_integrity'].values())} fetched ranges match the SHA-256 in their receipts ({hash_bad} mismatches). No pixel TRIDENT read from these copies can be missing data. This replaces the planned all-zero pixel check with a stronger byte-level one.</p>
{table(runs(), ['arm', 'seg', 'device', 'n', 'scanners', 'seconds', 'levels', 'art'], ['run', 'segmenter', 'device', 'scans', 'scanner', 'seconds', 'level read', 'artifact-model level'], num=('n', 'seconds'))}
<p><b>Repeatability:</b> KR_AT2 and KR_GT450 segmented a second time with HEST give regions with zero symmetric difference from the first run (criterion: areas within 0.1%). Pass.</p>
<p><b>Level path:</b> for HEST at 10x, AT2 (level downsamples 1, 4, 16, 32) is read from level 1 directly. GT450 (1, 4, 16, 64) has its level 1 at a downsample of 4.0, outside the 0.1 tolerance of the wanted 3.815, so TRIDENT reads level 0 and downsamples by 3.815. GrandQC reads AT2 at level 3 and GT450 at level 2. The two scanners therefore reach the same model through different reading paths.</p>
</section>

<section><h2>4. Readings 1 to 3: summary</h2>
{table(summ_rows, ['tool', 'sw', 'split', 'msf', 'med', 'rng', 'sm', 'ne'], ['tool', 'fields switched', 'AT2-only / GT450-only', 'mean section switch fraction', 'median GT450/AT2 area', 'range', 'GT450 smaller', 'region below 10% of its pair'], num=('sw', 'msf', 'med'))}
<figure>{chart_switch()}<figcaption>Fields whose admission differs between the two scans of the same section, out of 156. The HistoQC row is context from the earlier study, which uses HistoQC's usable-tissue mask, not a TRIDENT segmenter.</figcaption></figure>
<figure>{legend}{chart_ratio()}<figcaption>GT450 tissue area divided by AT2 tissue area, per section and segmenter. Hover a dot for the areas. Otsu's HR point sits at {HR['otsu']['GT450_over_AT2']}.</figcaption></figure>
</section>

<section><h2>5. Which fields switch</h2>
<p>For HEST, GrandQC and the artifact arm every switched field is listed. A fraction near 0 on one scan and near 1 on the other means a whole tissue core (or the part holding that field) is in one region and absent from the other; this is the case for {whole('hest')} of HEST's {S['hest']['switched']} and {whole('grandqc')} of GrandQC's {S['grandqc']['switched']}{(f", and {whole('hest_artifacts')} of the {S['hest_artifacts']['switched']} with artifact removal (section 7)" if 'hest_artifacts' in S else '')}. Otsu's {S['otsu']['switched']} switched fields are in <code>results/fields.csv</code>; {otsu_whole} of them are of the whole-core kind, and {sum(1 for f in otsu_sw if f['section']=='HR')} are in section HR.</p>
{table(sw_rows, ['tool', 'section', 'field', 'a', 'b', 'side'], ['tool', 'section', 'field', 'fraction inside, AT2', 'fraction inside, GT450', 'admitted on'], num=('field', 'a', 'b'))}
</section>

<section><h2>6. What the regions look like</h2>
<p>Section HR is the darkest-stained section on both scanners, and AT2 renders every section darker than GT450. Median tissue brightness (luma 0 to 255, 2000-pixel thumbnail, <code>results/brightness.csv</code>): HR {BR['HR_AT2']} on AT2 and {BR['HR_GT450']} on GT450; the other 12 sections {br_other('AT2')[0]} to {br_other('AT2')[-1]} on AT2 and {br_other('GT450')[0]} to {br_other('GT450')[-1]} on GT450. HEST's AT2 region for HR is {HR['hest']['AT2_mm2']} mm² against {HR['hest']['GT450_mm2']} mm² on GT450; Otsu's is {HR['otsu']['AT2_mm2']} against {HR['otsu']['GT450_mm2']}; GrandQC's is {HR['grandqc']['AT2_mm2']} against {HR['grandqc']['GT450_mm2']}. On the HEST contour overlay, the dark AT2 scan has straight-edged gaps cut into many cores; the GT450 scan of the same section has few.</p>
<p>A tiling cause was checked: long axis-aligned contour edges on HEST HR_AT2 (116 edges) were compared with the 512-pixel model input grid (2048 level-0 pixels, starting at the slide origin). One lies within 16 pixels of a grid line, and their positions modulo 2048 are spread across the range. The straight edges are not explained by the model tiles. They may come from the contour step, which resizes the mask to 2000 rows; this was not tested.</p>
<figure>{img('figs/check_hest_HR_KRH.jpg', 'HEST contours on HR and KRH, both scanners')}<figcaption>TRIDENT's own contour overlays, HEST. Top: HR on AT2 (left) and GT450 (right). Bottom: KRH on AT2 (left) and GT450 (right).</figcaption></figure>
<figure>{img('figs/check_contours.jpg', 'GrandQC and Otsu contours')}<figcaption>Earlier check image: GrandQC on KR_AT2, and Otsu on KR and HR for both scanners.</figcaption></figure>
</section>

<section><h2>7. Secondary readings</h2>
<p><b>Minimum piece size.</b> <code>mask_to_gdf</code> resizes the mask to 2000 rows and drops pieces below <code>min_contour_area=1000</code> scaled by mpp². In physical terms the threshold is 1000 × (slide height in µm / 2000)² and so depends on the slide's height, not only its resolution. Median across the 13 sections: {med(mpA):.4f} mm² on AT2, {med(mpB):.4f} mm² on GT450 (range {mpA[0]:.4f} to {mpA[-1]:.4f} and {mpB[0]:.4f} to {mpB[-1]:.4f}). The smallest piece kept differs between the two scans of the same glass.</p>
<p><b>Artifact-removal device.</b> <code>Processor.run_segmentation_job</code> passes <code>device</code> and <code>batch_size</code> to the tissue segmenter but not to the artifact model, whose <code>segment_tissue</code> call then uses the defaults <code>device='cuda:0'</code>, <code>batch_size=16</code>. On this machine the first run stopped with "Torch not compiled with CUDA enabled". On a multi-GPU machine, the same line would send the artifact model to <code>cuda:0</code> whatever <code>--gpu</code> was given (inferred from the code, not run). An open pull request, mahmoodlab/TRIDENT#237 (7 September 2026, another contributor), already passes <code>device</code> to this call, together with MPS routing and macOS data loading; it does not pass <code>batch_size</code>.</p>
<p><b>HEST with remove_artifacts</b> (secondary arm; HEST at defaults, then TRIDENT's GrandQC artifact model at 10x, which removes regions it classes as artifact): {art_status}.</p>
{art_block}
</section>

<section><h2>8. Deviations and incidents</h2>
<ul>
<li>Device: MPS instead of CUDA for HEST and GrandQC (Plan, as written).</li>
<li>Data-loader workers 0 (Addendum 2). Artifact-step device patched at run time (Addendum 3); the partial output of the failed first attempt was deleted before the rerun.</li>
<li>The planned all-zero pixel check was replaced by a byte-level check of fetched ranges and receipt hashes (section 3), done in the second pass.</li>
<li>Second pass, 19 November (<code>scripts/05_checks.py</code>, <code>results/checks.json</code>): an independent re-scoring by 40 × 40 point sampling in each field reproduces every field decision ({', '.join(f"{k} {v['switched']}" for k, v in CK['independent_rescore_point_sampling'].items())} switched; 0 decision mismatches; no fraction differs by more than 0.03). Field polygons measure {CK['field_side_um_AT2_then_GT450'][0]} and {CK['field_side_um_AT2_then_GT450'][1]} µm a side on AT2 and GT450, confirming the scanner order in the field maps. The HistoQC context figure recounts from that study's own field table as {CK['histoqc_context_recount']['switched']} ({CK['histoqc_context_recount']['AT2_only']} AT2-only, {CK['histoqc_context_recount']['GT450_only']} GT450-only). The first draft called HR's AT2 scan "unusually dark"; measured brightness shows HR is the darkest section on both scanners, and the wording was corrected.</li>
<li>A background wait loop meant to start HEST GT450 after HEST AT2 matched its own command line and never released; it was stopped and the runs started directly. No data effect.</li>
<li>After the artifact arm finished, a repeat of it on HR and MY (both scanners) was added before posting, to check run-to-run stability. This check was not in the plan; result in section 7.</li>
<li>A tile-grid explanation for the straight-edged gaps was checked after seeing the overlays and is not supported (section 6). This check was not in the plan.</li>
</ul></section>

<section><h2>9. Scope</h2>
<p>One tissue array, two scanners from one vendor, 13 serial and differently stained sections from shared tissue. Descriptive only, with no inference to other patients, scanners or vendors. Neither scanner nor any segmenter is taken as correct: a change between scanners says which tool is sensitive here, not which region is right. The field rule is ours; TRIDENT's own patching uses <code>min_tissue_proportion</code>, default 0. No private Parallax measurements are used.</p>
</section>

<section><h2>10. Files</h2>
<p><code>PLAN.md</code>, <code>ADDENDUM_1-3.md</code> with hashes; <code>scripts/01_download_gt450.py</code>, <code>02_segment.py</code>, <code>03_score.py</code>, <code>04_labbook.py</code>, <code>05_checks.py</code>, <code>06_artifact_fig.py</code>, <code>07_artifact_repeat.py</code>; <code>out/&lt;arm&gt;/</code> TRIDENT job folders with <code>run_meta_*.json</code>; <code>results/fields.csv</code>, <code>sections.csv</code>, <code>scans.csv</code>, <code>summary.json</code>; <code>logs/</code>; <code>figs/</code>.</p>
<details><summary>Per-section table, all segmenters</summary>
{table(sec_rows, ['tool', 'section', 'n', 'both_in', 'a', 'b', 'out', 'A', 'B', 'r'], ['tool', 'section', 'fields', 'both in', 'AT2 only', 'GT450 only', 'both out', 'AT2 mm²', 'GT450 mm²', 'GT450/AT2'], num=('n', 'both_in', 'a', 'b', 'out', 'A', 'B', 'r'))}
</details>
</section>
"""

css = """
:root{--bg:#fcfcfb;--fg:#0b0b0b;--fg2:#52514e;--muted:#a9a8a1;--line:#e8e7e3;--card:#f3f2ee;--s1:#2a78d6;--s2:#eb6834;--s3:#1baf7a}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--bg:#1a1a19;--fg:#f0efec;--fg2:#c3c2b7;--muted:#6f6e68;--line:#33332f;--card:#24241f;--s1:#3987e5;--s2:#d95926;--s3:#199e70}}
:root[data-theme="dark"]{--bg:#1a1a19;--fg:#f0efec;--fg2:#c3c2b7;--muted:#6f6e68;--line:#33332f;--card:#24241f;--s1:#3987e5;--s2:#d95926;--s3:#199e70}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:16px/1.55 ui-sans-serif,-apple-system,"Helvetica Neue",Arial,sans-serif}
main{max-width:860px;margin:0 auto;padding:32px 16px 80px}h1{font-size:1.7rem;line-height:1.25;margin:.2em 0 .5em}h2{font-size:1.15rem;margin:2.2em 0 .6em;padding-top:.6em;border-top:1px solid var(--line)}
.kicker{color:var(--fg2);font-size:.85rem;margin:0}.lede{color:var(--fg2);font-size:1.05rem}code{font:.86em ui-monospace,Menlo,monospace;background:var(--card);padding:1px 4px;border-radius:4px;overflow-wrap:anywhere}
.tw{overflow-x:auto;margin:1em 0}table{border-collapse:collapse;font-size:.86rem;width:100%}th,td{text-align:left;padding:5px 8px;border-bottom:1px solid var(--line);vertical-align:top}th{color:var(--fg2);font-weight:600}td.n,th.n{text-align:right;font-variant-numeric:tabular-nums}
figure{margin:1.4em 0}figcaption{color:var(--fg2);font-size:.86rem;margin-top:.4em}svg{width:100%;height:auto;display:block}
.grid{stroke:var(--line);stroke-width:1}.axis{stroke:var(--muted);stroke-width:1.5}.tick{fill:var(--fg2);font-size:11px}.lab{fill:var(--fg);font-size:12px}.val{fill:var(--fg);font-size:12px;font-variant-numeric:tabular-nums}
.hov:hover circle:first-child,.hov:hover rect{opacity:.8}.legend{display:flex;gap:16px;flex-wrap:wrap;font-size:.86rem;color:var(--fg2)}.legend i{display:inline-block;width:10px;height:10px;border-radius:50%;margin-right:6px}
details summary{cursor:pointer;color:var(--fg2)}
"""
doc = f'<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>TRIDENT PLISM Lab Book</title><style>{css}</style></head><body><main>{body}</main></body></html>'
(ROOT / 'LABBOOK.html').write_text(doc)
print('LABBOOK.html', len(doc) // 1024, 'KB')
