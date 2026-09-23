from pathlib import Path, PurePosixPath
import collections, hashlib, json, zipfile, time

ROOT = Path(__file__).resolve().parent
source = ROOT.parent
inventory = []
for p in sorted(source.glob('*.apk*')):
    if not p.is_file():
        continue
    slug = 'game300_2018' if '300' in p.name else ('ciyuan_2017' if '2017' in p.name else 'moba_2016')
    dest = ROOT / slug / 'unpacked'
    dest.mkdir(parents=True, exist_ok=True)
    digest = hashlib.file_digest(p.open('rb'), 'sha256').hexdigest()
    files = []
    with zipfile.ZipFile(p) as z:
        for entry in z.infolist():
            name = entry.filename
            posix = PurePosixPath(name)
            if posix.is_absolute() or '..' in posix.parts or '\\' in name or ':' in name:
                raise ValueError('Unsafe ZIP path: ' + name)
            out = dest.joinpath(*posix.parts)
            if entry.is_dir():
                out.mkdir(parents=True, exist_ok=True)
                continue
            data = z.read(entry)  # Reads and checks each ZIP entry's CRC.
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_bytes(data)
            files.append({'path': name, 'size':len(data), 'compressed_size':entry.compress_size,
                          'sha256':hashlib.sha256(data).hexdigest()})
    info = {'source':p.name, 'id':slug, 'size':p.stat().st_size, 'sha256':digest,
            'file_count':len(files), 'uncompressed_size':sum(x['size'] for x in files),
            'extensions':dict(collections.Counter(PurePosixPath(x['path']).suffix for x in files)),
            'asset_groups':dict(collections.Counter('/'.join(x['path'].split('/')[:3]) for x in files if x['path'].startswith('assets/'))),
            'files':files, 'zip_crc':'all entries passed'}
    (ROOT / slug / 'inventory.json').write_text(json.dumps(info, ensure_ascii=False, indent=2), encoding='utf-8')
    inventory.append(info)
    print(json.dumps({k:v for k,v in info.items() if k not in ('files','asset_groups')}, ensure_ascii=False), flush=True)
comparison=[]
for i,a in enumerate(inventory):
    for b in inventory[i+1:]:
        af={x['path']:x for x in a['files'] if x['path'].startswith('assets/')}
        bf={x['path']:x for x in b['files'] if x['path'].startswith('assets/')}
        common=sorted(af.keys() & bf.keys())
        same=[n for n in common if af[n]['sha256']==bf[n]['sha256']]
        comparison.append({'a':a['id'],'b':b['id'],'common_asset_paths':len(common),
                           'identical_assets':len(same),'identical_asset_examples':same[:50],
                           'identical_asset_paths':same})
(ROOT/'comparison.json').write_text(json.dumps(comparison,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps([{k:v for k,v in x.items() if k!='identical_asset_paths'} for x in comparison],ensure_ascii=False),flush=True)
