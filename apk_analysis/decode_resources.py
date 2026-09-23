from pathlib import Path
import struct, zlib, zipfile, json, hashlib, collections

ROOT=Path(__file__).resolve().parent
# Key is read from the resource loader in this exact 2017 native library.
core=(ROOT/'ciyuan_2017/unpacked/lib/armeabi/libgame.so').read_bytes()
shoff=struct.unpack_from('<I',core,32)[0]
shnum=struct.unpack_from('<H',core,48)[0]
sections=[struct.unpack_from('<10I',core,shoff+40*i) for i in range(shnum)]
def read_vaddr(addr,count):
    s=next(s for s in sections if s[1]!=8 and s[3]<=addr<s[3]+s[5])
    off=addr-s[3]+s[4];return core[off:off+count]
key_addr=(0x6d21fc+struct.unpack('<I',read_vaddr(0x6d238c,4))[0])&0xffffffff
key=read_vaddr(key_addr,128).split(b'\0')[0]
assert len(key)==32
tables=[bytes(c^k for c in range(256)) for k in key]
results=[]
for parent in sorted(ROOT.glob('*/inventory.json')):
    info=json.loads(parent.read_text(encoding='utf-8'));out=parent.parent/'decoded'
    out.mkdir(exist_ok=True);files=[];errors=[];wrapped_count=0
    with zipfile.ZipFile(ROOT.parent/info['source']) as z:
        for item in info['files']:
            name=item['path']
            if not name.startswith('assets/'):continue
            data=z.read(name);wrapped=data.startswith(b'MP:')
            if wrapped:
                try:
                    expected=struct.unpack_from('<I',data,4)[0]
                    if expected>256*2**20:raise ValueError('Unexpectedly large resource')
                    buf=bytearray(data[12:])
                    for i,t in enumerate(tables):buf[i::len(key)]=buf[i::len(key)].translate(t)
                    decoder=zlib.decompressobj();data=decoder.decompress(buf,expected+1)
                    if not decoder.eof or decoder.unused_data or len(data)!=expected:
                        raise ValueError('Resource length or zlib stream validation failed')
                    wrapped_count+=1
                except Exception as e:
                    errors.append({'path':name,'error':str(e)});continue
            p=out/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data)
            files.append({'path':name,'size':len(data),'sha256':hashlib.sha256(data).hexdigest(),'was_wrapped':wrapped})
    result={'id':info['id'],'resource_count':len(files),'decoded_mp_files':wrapped_count,
            'decoded_bytes':sum(x['size'] for x in files),'errors':errors,'files':files}
    (parent.parent/'decoded_inventory.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    results.append(result)
    print(json.dumps({k:v for k,v in result.items() if k!='files'},ensure_ascii=False),flush=True)
comparisons=[]
for i,a in enumerate(results):
    for b in results[i+1:]:
        af={x['path']:x for x in a['files']};bf={x['path']:x for x in b['files']}
        common=sorted(af.keys() & bf.keys())
        same=[p for p in common if af[p]['sha256']==bf[p]['sha256']]
        comparisons.append({'a':a['id'],'b':b['id'],'common_paths':len(common),
                            'identical_decoded_assets':len(same),'identical_by_extension':dict(collections.Counter(Path(p).suffix for p in same)),
                            'identical_paths':same})
(ROOT/'decoded_comparison.json').write_text(json.dumps(comparisons,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps([{k:v for k,v in x.items() if k!='identical_paths'} for x in comparisons],ensure_ascii=False),flush=True)
