"""Download complete GT450 PLISM scans from figshare and verify MD5 (Addendum 1)."""
import json, hashlib, sys, time, requests
from pathlib import Path
META = Path('/Volumes/Temp_flex/parallax_pathology/HUMAN_SCANNER_REPLICATION_20261110/files_24988074.json')
OUT = Path('/Volumes/Temp_flex/parallax_pathology/TRIDENT_PLISM_20261118/full')
rows = [r for r in json.load(open(META))['files'] if r['name'].endswith('_GT450.svs')]
assert len(rows) == 13
for r in sorted(rows, key=lambda r: r['name']):
    dst = OUT / r['name']
    if dst.exists() and dst.stat().st_size == r['size']:
        print('have', r['name'], flush=True); continue
    for attempt in range(4):
        try:
            h = hashlib.md5(); tmp = dst.with_suffix('.partial')
            with requests.get(r['download_url'], stream=True, timeout=120) as resp, open(tmp, 'wb') as f:
                resp.raise_for_status()
                for chunk in resp.iter_content(1 << 22):
                    f.write(chunk); h.update(chunk)
            assert tmp.stat().st_size == r['size'], 'size'
            assert h.hexdigest() == r['computed_md5'], 'md5'
            tmp.rename(dst); print('ok', r['name'], h.hexdigest(), flush=True); break
        except Exception as e:
            print('retry', r['name'], repr(e), flush=True); time.sleep(10 * (attempt + 1))
    else:
        sys.exit('failed ' + r['name'])
print('done', flush=True)
