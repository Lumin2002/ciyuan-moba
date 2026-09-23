from pathlib import Path
import struct, json, re, collections, hashlib
from xml.etree import ElementTree as ET
from cryptography.hazmat.primitives.serialization import pkcs7
from cryptography.hazmat.primitives import hashes

ROOT=Path(__file__).resolve().parent
ANDROID='http://schemas.android.com/apk/res/android'
ET.register_namespace('android',ANDROID)
def u16(b,p):return struct.unpack_from('<H',b,p)[0]
def u32(b,p):return struct.unpack_from('<I',b,p)[0]
def string_pool(b,off):
    head=u16(b,off+2); count=u32(b,off+8); flags=u32(b,off+16); start=u32(b,off+20)
    out=[]
    for i in range(count):
        p=off+start+u32(b,off+head+4*i)
        if flags&0x100:
            n=b[p]; p+=2 if n&0x80 else 1
            n=b[p]; p+=1
            if n&0x80:n=((n&0x7f)<<8)|b[p];p+=1
            out.append(b[p:p+n].decode('utf-8','replace'))
        else:
            n=u16(b,p);p+=2
            if n&0x8000:n=((n&0x7fff)<<16)|u16(b,p);p+=2
            out.append(b[p:p+n*2].decode('utf-16le','replace'))
    return out
def typed_value(b,p,pool):
    typ=b[p+3];val=u32(b,p+4)
    if typ==3:return pool[val]
    if typ==1:return '@0x%08x'%val
    if typ==2:return '?0x%08x'%val
    if typ==0x12:return 'true' if val else 'false'
    if typ==0x11:return '0x%x'%val
    if typ==0x10:return str(val if val<0x80000000 else val-0x100000000)
    if 0x1c<=typ<=0x1f:return '#%08x'%val
    if typ==4:return str(struct.unpack('<f',struct.pack('<I',val))[0])
    return str(val)
def axml(b):
    pool=[]; stack=[];root=None;pos=u16(b,2)
    while pos<len(b):
        typ=u16(b,pos);h=u16(b,pos+2);size=u32(b,pos+4)
        if size<h or size==0:raise ValueError('Invalid XML chunk')
        if typ==1:pool=string_pool(b,pos)
        elif typ==0x102:
            ext=pos+h; ns=u32(b,ext);name=u32(b,ext+4)
            tag=pool[name] if ns==0xffffffff else '{'+pool[ns]+'}'+pool[name]
            el=ET.Element(tag);aoff=u16(b,ext+8);asz=u16(b,ext+10);count=u16(b,ext+12)
            for i in range(count):
                p=ext+aoff+i*asz;an=u32(b,p);ai=u32(b,p+4);raw=u32(b,p+8)
                key=pool[ai] if an==0xffffffff else '{'+pool[an]+'}'+pool[ai]
                el.set(key,pool[raw] if raw!=0xffffffff else typed_value(b,p+12,pool))
            if stack:stack[-1].append(el)
            else:root=el
            stack.append(el)
        elif typ==0x103:stack.pop()
        pos+=size
    return root
def resources(b):
    global_pool=[];result={};pos=u16(b,2)
    while pos<len(b):
        typ=u16(b,pos);head=u16(b,pos+2);size=u32(b,pos+4)
        if not size:break
        if typ==1:global_pool=string_pool(b,pos)
        elif typ==0x200:
            package=u32(b,pos+8); type_shift=u32(b,pos+284) if head>=288 else 0
            types=string_pool(b,pos+u32(b,pos+268)); keys=string_pool(b,pos+u32(b,pos+276))
            q=pos+head
            while q<pos+size:
                t=u16(b,q);hh=u16(b,q+2);sz=u32(b,q+4)
                if not sz:break
                if t==0x201:
                    tid=b[q+8];flags=b[q+9];n=u32(b,q+12);start=u32(b,q+16)
                    if flags:raise ValueError('Sparse ARSC unsupported')
                    for i in range(n):
                        entryoff=u32(b,q+hh+4*i)
                        if entryoff==0xffffffff:continue
                        e=q+start+entryoff;eh=u16(b,e);ef=u16(b,e+2);ki=u32(b,e+4)
                        if ef&1:continue
                        rid=(package<<24)|((tid+type_shift)<<16)|i
                        record={'name':types[tid-1]+'/'+keys[ki], 'value':typed_value(b,e+eh,global_pool)}
                        if record not in result.setdefault('@0x%08x'%rid,[]):result['@0x%08x'%rid].append(record)
                q+=sz
        pos+=size
    return result
def dex_info(b):
    count=u32(b,56);off=u32(b,60); strings=[]
    for i in range(count):
        p=u32(b,off+i*4)
        while b[p]&0x80:p+=1
        p+=1;end=b.index(0,p)
        strings.append(b[p:end].decode('utf-8','replace'))
    ntypes=u32(b,64);toff=u32(b,68)
    types=[strings[u32(b,toff+4*i)] for i in range(ntypes)]
    nclasses=u32(b,96);coff=u32(b,100)
    classes=[types[u32(b,coff+32*i)] for i in range(nclasses)]
    return strings,classes
def attrs(el):return {k.replace('{'+ANDROID+'}','android:'):v for k,v in el.attrib.items()}
def save(path,data):path.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
url_re=re.compile(rb'https?://[A-Za-z0-9][A-Za-z0-9.\-_:]*(?:/[^\x00-\x20\x7f-\xff<>"\x27\\]*)?')
results=[]
for d in sorted(ROOT.glob('*/unpacked')):
    out=d.parent;inv=json.loads((out/'inventory.json').read_text(encoding='utf-8'))
    manifest=axml((d/'AndroidManifest.xml').read_bytes())
    ET.indent(manifest)
    ET.ElementTree(manifest).write(out/'AndroidManifest.decoded.xml',encoding='utf-8',xml_declaration=True)
    res=resources((d/'resources.arsc').read_bytes());save(out/'resources.json',res)
    def resolve(value):return res.get(value,[{'value':value}])
    app=manifest.find('application'); sdk=manifest.find('uses-sdk')
    info={k:inv[k] for k in ['id','source','size','sha256','file_count','zip_crc']}
    info.update({'manifest':attrs(manifest),'sdk':attrs(sdk) if sdk is not None else {},'application':attrs(app),
                 'app_labels':resolve(app.get('{'+ANDROID+'}label','')),
                 'icons':resolve(app.get('{'+ANDROID+'}icon','')),
                 'permissions':[attrs(x) for x in manifest.findall('uses-permission')],
                 'features':[attrs(x) for x in manifest.findall('uses-feature')],
                 'components':[{'type':x.tag,**attrs(x),'intent_actions':[a.get('{'+ANDROID+'}name') for a in x.findall('intent-filter/action')]} for x in app if x.tag in ['activity','service','receiver','provider']],
                 'metadata':[attrs(x) for x in app.findall('meta-data')]})
    certificates=[]
    for p in (d/'META-INF').glob('*.RSA'):
        for cert in pkcs7.load_der_pkcs7_certificates(p.read_bytes()):
            certificates.append({'file':p.name,'subject':cert.subject.rfc4514_string(),'issuer':cert.issuer.rfc4514_string(),
                                 'sha256':cert.fingerprint(hashes.SHA256()).hex(),
                                 'not_before':str(cert.not_valid_before_utc),'not_after':str(cert.not_valid_after_utc),
                                 'signature_algorithm':cert.signature_hash_algorithm.name})
    info['certificates']=certificates
    ds,classes=dex_info((d/'classes.dex').read_bytes())
    (out/'dex_classes.txt').write_text('\n'.join(classes),encoding='utf-8')
    (out/'dex_strings.txt').write_text('\n'.join(ds),encoding='utf-8')
    info['dex']={'classes':len(classes),'strings':len(ds),'magic':(d/'classes.dex').read_bytes()[:8].hex(),
                 'class_groups':dict(collections.Counter('/'.join(s[1:].split('/')[:3]) for s in classes).most_common(45))}
    libs=[]; native_markers=[]
    for p in (d/'lib').rglob('*.so'):
        b=p.read_bytes();libs.append({'path':p.relative_to(d).as_posix(),'size':len(b),'elf_class':b[4],'machine':u16(b,18)})
        if p.name in ['libgame.so','libtombird.so']:
            strings=[s.decode('ascii') for s in re.findall(rb'[\x20-\x7e]{6,}',b)]
            (out/'native_core_strings.txt').write_text('\n'.join(strings),encoding='utf-8')
            native_markers=[s for s in strings if any(t in s for t in ['Lua 5.','LuaJIT 2.','cocos2d-x','cn/emagroup/kom/Tombird']) and len(s)<150]
    info['libraries']=libs;info['native_markers']=native_markers
    urls=collections.defaultdict(set);wrapped=collections.Counter();unwrapped=collections.Counter();samples={}
    for item in inv['files']:
        rel=item['path'];p=d/rel
        # Inspect all game resource headers; collect URLs from plausible code/config containers.
        if rel.startswith('assets/data/'):
            with p.open('rb') as f:head=f.read(16)
            key=p.suffix
            (wrapped if head.startswith(b'MP:') else unwrapped)[key]+=1
            samples.setdefault(key,{'path':rel,'header':head.hex()})
        if p.suffix.lower() in ['.dex','.so','.lua','.json','.xml','.txt','.ini','.properties','.cfg','.csv','.proto','.sh','.h']:
            b=p.read_bytes()
            if b.startswith(b'MP:'):continue
            for m in url_re.finditer(b):
                u=m.group().decode('ascii').rstrip('),;]}')
                if len(u)<=1000:urls[u].add(rel)
    network=[{'url':u,'sources':sorted(paths)} for u,paths in sorted(urls.items())]
    save(out/'network_strings.json',network)
    info['network_string_count']=len(network)
    info['resource_wrapping']={'wrapped_by_extension':dict(wrapped),'unwrapped_by_extension':dict(unwrapped),'header_samples':samples}
    info['config']=(d/'assets/config/config.lua').read_text(encoding='utf-8-sig')
    save(out/'summary.json',info);results.append(info)
    print(json.dumps({k:info[k] for k in ['id','manifest','sdk','app_labels','icons','permissions','certificates','native_markers','resource_wrapping']},ensure_ascii=False),flush=True)
save(ROOT/'summary.json',results)
