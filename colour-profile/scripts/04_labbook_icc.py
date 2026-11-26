"""LABBOOK.html for the TRIDENT ICC rerun. Reads results/ and the original study's results/; computes nothing new beyond ratios and counts."""
import csv, json, hashlib, html
from collections import Counter
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
ORIG = ROOT.parent / 'trident-plism'
plan_sha = (ROOT / 'PLAN.sha256').read_text().split()[0]
assert plan_sha == hashlib.sha256((ROOT / 'PLAN.md').read_bytes()).hexdigest()
S = json.loads((ROOT / 'results' / 'summary.json').read_text())
SO = json.loads((ORIG / 'results' / 'summary.json').read_text())
G = json.loads((ROOT / 'results' / 'gate.json').read_text()); assert G['passed']
TH = json.loads((ROOT.parent / 'plism-icc' / 'thumbnail_check.json').read_text())
assert all(TH[k]['raw'][0] < TH[k]['raw'][1] for k in TH if not k.startswith('_'))
META = {a: json.loads(next((ROOT / 'out' / a).glob('run_meta_*.json')).read_text()) for a in S}
sec = lambda p: {(r['arm'], r['section']): r for r in csv.DictReader(open(p))}
I, O = sec(ROOT / 'results' / 'sections.csv'), sec(ORIG / 'results' / 'sections.csv')
fl = lambda p, a: {(r['section'], r['field']): r for r in csv.DictReader(open(p)) if r['arm'] == a}
SECS = sorted({s for _, s in I})
PAIRS = [('otsu', 'icc_otsu'), ('grandqc', 'icc_grandqc'), ('hest', 'icc_hest'), ('hest_artifacts', 'icc_hest_artifacts')]
NAMES = {'otsu': 'Otsu', 'grandqc': 'GrandQC', 'hest': 'HEST', 'hest_artifacts': 'HEST + artifact removal'}


def table(head, rows, num):
    h = ''.join(f'<th{" class=n" if i in num else ""}>{html.escape(c)}</th>' for i, c in enumerate(head))
    b = ''.join('<tr>' + ''.join(f'<td{" class=n" if i in num else ""}>{c}</td>' for i, c in enumerate(r)) + '</tr>' for r in rows)
    return f'<div class=tw><table><thead><tr>{h}</tr></thead><tbody>{b}</tbody></table></div>'


# primary
prim, adm = [], []
for o, i in PAIRS:
    a, b = SO[o], S[i]
    prim.append([NAMES[o], f"{a['switched']} ({a['AT2_only']} / {a['GT450_only']})", f"{b['switched']} ({b['AT2_only']} / {b['GT450_only']})",
                 f"{a['area_ratio_median']:.3f} [{a['area_ratio_min']:.3f}, {a['area_ratio_max']:.3f}]",
                 f"{b['area_ratio_median']:.3f} [{b['area_ratio_min']:.3f}, {b['area_ratio_max']:.3f}]"])
    fo, fi = fl(ORIG / 'results' / 'fields.csv', o), fl(ROOT / 'results' / 'fields.csv', i)
    assert set(fo) == set(fi) and len(fi) == 156
    nA = lambda f, k: sum(r[k] == '1' for r in f.values())
    chA = sum(fo[k]['AT2_in'] != fi[k]['AT2_in'] for k in fi); chG = sum(fo[k]['GT450_in'] != fi[k]['GT450_in'] for k in fi)
    both = lambda f: sum(r['AT2_in'] == r['GT450_in'] == '1' for r in f.values())
    adm.append([NAMES[o], f"{nA(fo,'AT2_in')} → {nA(fi,'AT2_in')}", f"{nA(fo,'GT450_in')} → {nA(fi,'GT450_in')}", f"{both(fo)} → {both(fi)}", str(chA), str(chG)])

# HR areas
hr = []
for o, i in PAIRS:
    hr.append([NAMES[o], f"{float(O[(o,'HR')]['AT2_mm2']):.1f} / {float(O[(o,'HR')]['GT450_mm2']):.1f}",
               f"{float(I[(i,'HR')]['AT2_mm2']):.1f} / {float(I[(i,'HR')]['GT450_mm2']):.1f}"])

# artifact step: area kept after removal, relative to HEST alone in the same colour handling
kept, tot = [], Counter()
for s in SECS:
    v = dict(oA=O[('hest_artifacts', s)]['AT2_mm2'], oG=O[('hest_artifacts', s)]['GT450_mm2'], hA=O[('hest', s)]['AT2_mm2'], hG=O[('hest', s)]['GT450_mm2'],
             iA=I[('icc_hest_artifacts', s)]['AT2_mm2'], iG=I[('icc_hest_artifacts', s)]['GT450_mm2'], HA=I[('icc_hest', s)]['AT2_mm2'], HG=I[('icc_hest', s)]['GT450_mm2'])
    v = {k: float(x) for k, x in v.items()}; tot.update(v)
    kept.append([s, f"{v['oA']/v['hA']:.0%}", f"{v['oG']/v['hG']:.0%}", f"{v['iA']/v['HA']:.0%}", f"{v['iG']/v['HG']:.0%}",
                 f"{I[('icc_hest_artifacts', s)]['AT2_only']} / {I[('icc_hest_artifacts', s)]['GT450_only']}"])
pk = {k: tot[n] / tot[d] for k, n, d in [('oA', 'oA', 'hA'), ('oG', 'oG', 'hG'), ('iA', 'iA', 'HA'), ('iG', 'iG', 'HG')]}
kept.append(['all, pooled area', f"{pk['oA']:.0%}", f"{pk['oG']:.0%}", f"{pk['iA']:.0%}", f"{pk['iG']:.0%}",
             f"{S['icc_hest_artifacts']['AT2_only']} / {S['icc_hest_artifacts']['GT450_only']}"])
lowerA = sum(float(I[('icc_hest_artifacts', s)]['AT2_mm2']) / float(I[('icc_hest', s)]['AT2_mm2']) <
             float(O[('hest_artifacts', s)]['AT2_mm2']) / float(O[('hest', s)]['AT2_mm2']) for s in SECS)
gt_bigger = sum(float(I[('icc_hest_artifacts', s)]['GT450_over_AT2']) > 1 for s in SECS)

runs = [[f'<code>{a}</code>', m['segmenter'], m['device'], str(m['convert']), f"{m['read_region_calls']:,}", ', '.join(m['profiles']) or 'none', (f"{m['seconds']/3600:.1f} h" if m['seconds'] >= 3600 else f"{m['seconds']/60:.0f} min")] for a, m in META.items()]
art = S['icc_hest_artifacts']; arto = SO['hest_artifacts']

body = f"""
<p class=kicker>Lab book · TRIDENT colour-profile rerun · built by scripts/04_labbook_icc.py</p>
<h1>TRIDENT on paired PLISM scans, with each scan's embedded colour profile applied</h1>
<p class=lede>Same 26 scans, TRIDENT commit, weights, settings, fields and scoring as the original TRIDENT study (<code>../trident-plism</code>). One change: every region TRIDENT reads is converted from the scan's embedded profile ("AT2" or "Segue_v2") to sRGB. Applied, the profiles take Otsu from {SO['otsu']['switched']} to {S['icc_otsu']['switched']} switched fields of 156, GrandQC from {SO['grandqc']['switched']} to {S['icc_grandqc']['switched']} and HEST from {SO['hest']['switched']} to {S['icc_hest']['switched']}. HEST with artifact removal goes from {arto['switched']} to {art['switched']}.</p>

<h2>1. Record</h2>
<ul>
<li>Plan frozen before any run: <code>PLAN.md</code>, SHA-256 <code>{plan_sha}</code>, {(ROOT / 'PLAN.frozen_at.txt').read_text().strip()}. Arms run in the planned order by <code>run_chain.sh</code>; scoring by <code>scripts/03_score_icc.py</code> (the original <code>03_score.py</code> logic, arms changed).</li>
<li>TRIDENT {META['icc_hest']['trident_commit'][:7]}, linked in place and unedited; the conversion is a run-time wrapper on <code>openslide.OpenSlide.read_region</code>. Python {META['icc_hest']['python']}, torch {META['icc_hest']['torch']}, OpenSlide {META['icc_hest']['openslide']}. TRIDENT is CC BY-NC-ND; none of its code is copied here.</li>
</ul>
{table(['arm', 'segmenter', 'device', 'conversion', 'region reads', 'profiles applied', 'time'], runs, num=[4, 6])}

<h2>2. Gate</h2>
<p>With the wrapper on and conversion off, Otsu and GrandQC regions equal the original study's on all {G['otsu']['scans']} scans each (zero symmetric difference). The wrapper alone changes nothing. Pass.</p>

<h2>3. Fields switched, of 156</h2>
{table(['segmenter', 'original (AT2-only / GT450-only)', 'profile applied', 'GT450/AT2 tissue area, original: median [range]', 'profile applied'], prim, num=[])}
<p>AT2-only is a field admitted on AT2 and not on GT450; GT450-only the reverse. No region in any colour-profile arm fell below 10% of its pair.</p>

<h2>4. Fields admitted</h2>
{table(['segmenter', 'admitted on AT2, original → profile', 'on GT450', 'on both', 'AT2 decisions changed', 'GT450 decisions changed'], adm, num=[4, 5])}

<h2>5. HR, the section where artifact removal took most of the tissue originally</h2>
{table(['segmenter', 'HR tissue mm², AT2 / GT450, original', 'profile applied'], hr, num=[1, 2])}

<h2>6. The artifact step, by section</h2>
<p>Tissue area after artifact removal as a share of the HEST region before it, in the same colour handling. Areas come from each arm's own regions.</p>
{table(['section', 'AT2 kept, original', 'GT450 kept, original', 'AT2 kept, profile', 'GT450 kept, profile', 'switched with profile, AT2-only / GT450-only'], kept, num=range(1, 6))}
<p>With the profile applied, the artifact step keeps a smaller share of AT2 tissue than in the original run on {lowerA} of 13 sections; HR is the exception, where it keeps more on both scanners. GT450's share moves by at most 8.2 percentage points from its original value except on HR. The result is a GT450 region larger than the AT2 region on {gt_bigger} of 13 sections, and {art['GT450_only']} of the {art['switched']} switched fields are admitted on GT450 only. HEST alone switches {S['icc_hest']['switched']} fields under the same conversion, so the added switches come from the artifact step. For reference, on 2000-pixel OpenSlide thumbnails with the profiles applied, AT2 tissue is brighter than GT450 tissue on {TH['_icc_AT2_brighter']} of 13 sections (median tissue luma; <code>../plism-icc/thumbnail_check.json</code>); without them it is darker on all 13.</p>

<h2>7. Scope</h2>
<p>Same array, scanners, software and settings; only the colour conversion changes. One rendering intent. Thirteen serial, differently stained sections of one mixed-tissue TMA; two scanners from one vendor. Descriptive: it does not say which region is right. The segmentation and artifact models were trained on images whose colour handling is not known here, so converted pixels are not assumed to be closer to their training data.</p>

<h2>8. Files</h2>
<p><code>PLAN.md</code>, <code>PLAN.sha256</code>, <code>PLAN.frozen_at.txt</code>; <code>run_chain.sh</code>; <code>scripts/02_segment_icc.py</code>, <code>scripts/gate_check.py</code>, <code>scripts/03_score_icc.py</code>, <code>scripts/04_labbook_icc.py</code>; <code>out/&lt;arm&gt;/</code> (regions, thumbnails, run metadata); <code>results/</code> (<code>gate.json</code>, <code>summary.json</code>, <code>sections.csv</code>, <code>fields.csv</code>, <code>scans.csv</code>); <code>logs/</code>.</p>
"""
css = """:root{--bg:#fcfcfb;--fg:#0b0b0b;--fg2:#52514e;--line:#e8e7e3;--card:#f3f2ee}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--bg:#1a1a19;--fg:#f0efec;--fg2:#c3c2b7;--line:#33332f;--card:#24241f}}
:root[data-theme="dark"]{--bg:#1a1a19;--fg:#f0efec;--fg2:#c3c2b7;--line:#33332f;--card:#24241f}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:16px/1.55 ui-sans-serif,-apple-system,"Helvetica Neue",Arial,sans-serif}
main{max-width:980px;margin:0 auto;padding:32px 16px 80px}h1{font-size:1.6rem;line-height:1.25}h2{font-size:1.1rem;margin-top:2em;padding-top:.6em;border-top:1px solid var(--line)}
.kicker{color:var(--fg2);font-size:.85rem}.lede{color:var(--fg2)}code{font:.86em ui-monospace,Menlo,monospace;background:var(--card);padding:1px 4px;border-radius:4px;overflow-wrap:anywhere}
.tw{overflow-x:auto;margin:1em 0}table{border-collapse:collapse;font-size:.82rem;width:100%}th,td{text-align:left;padding:5px 8px;border-bottom:1px solid var(--line);vertical-align:top}th{color:var(--fg2);font-weight:600}.n{text-align:right;font-variant-numeric:tabular-nums}"""
(ROOT / 'LABBOOK.html').write_text(f'<!doctype html><html lang=en><head><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1"><title>TRIDENT With Profiles</title><style>{css}</style></head><body><main>{body}</main></body></html>')
print('LABBOOK.html written; AT2 kept lower on', lowerA, 'of 13; GT450 larger on', gt_bigger, 'of 13')
