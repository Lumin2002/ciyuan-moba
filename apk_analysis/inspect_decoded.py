from pathlib import Path
import json,re,struct,collections
from PIL import Image,ImageDraw,ImageFont

ROOT=Path(__file__).resolve().parent
def varint(b,p):
    v=0;s=0
    while True:
        x=b[p];p+=1;v|=(x&127)<<s
        if not x&128:return v,p
        s+=7
        if s>70:raise ValueError('Invalid varint')
def protobuf_fields(b):
    p=0;out=[]
    while p<len(b):
        tag,p=varint(b,p);field=tag>>3;wire=tag&7
        if not field:raise ValueError('Zero field')
        if wire==0:v,p=varint(b,p)
        elif wire==1:v=b[p:p+8];p+=8
        elif wire==2:
            n,p=varint(b,p);v=b[p:p+n];p+=n
        elif wire==5:v=b[p:p+4];p+=4
        else:raise ValueError('Unsupported wire type')
        if p>len(b):raise ValueError('Truncated data')
        out.append((field,wire,v))
    return out
def text_value(b):
    if not isinstance(b,bytes):return b
    for enc in ['utf-8-sig','gb18030']:
        try:return b.decode(enc)
        except UnicodeError:pass
    return b.hex()
summaries=[]
for d in sorted(ROOT.glob('*/decoded')):
    out=d.parent;inv=json.loads((out/'decoded_inventory.json').read_text(encoding='utf-8'))
    heroes=[]
    for field,wire,b in protobuf_fields((d/'assets/data/conf/hero_c.dat').read_bytes()):
        if field!=1 or wire!=2:continue
        h={f:(w,v) for f,w,v in protobuf_fields(b)}
        heroes.append({'id':h.get(1,(0,None))[1],'name':text_value(h.get(7,(2,b''))[1])})
    lookup={}
    language_file=d/'assets/data/conf/string_client_c.dat'
    if language_file.is_file():
        for field,wire,b in protobuf_fields(language_file.read_bytes()):
            if field!=1 or wire!=2:continue
            values={f:v for f,w,v in protobuf_fields(b)}
            if isinstance(values.get(1),bytes) and isinstance(values.get(2),bytes):
                lookup[values[1].decode('ascii','replace')]=values[2].decode('gb18030','replace')
        (out/'localized_strings.json').write_text(json.dumps(lookup,ensure_ascii=False,indent=2),encoding='utf-8')
    for h in heroes:
        h['name_key']=h.pop('name');h['display_name']=lookup.get(h['name_key'])
    (out/'heroes.json').write_text(json.dumps(heroes,ensure_ascii=False,indent=2),encoding='utf-8')
    findings=[];versions={};lua_count=0;luatext_count=0
    for item in inv['files']:
        rel=item['path'];p=d/rel
        if p.suffix=='.lua':
            lua_count+=1
            if not p.read_bytes().startswith((b'\x1bLua',b'\x1bLJ')):luatext_count+=1
        if p.suffix in ['.lua','.json','.ini','.txt','.xml','.properties']:
            raw=p.read_bytes()
            try:t=raw.decode('utf-8-sig')
            except UnicodeError:continue
            for i,line in enumerate(t.splitlines(),1):
                if re.search(r'https?://|(?:\d{1,3}\.){3}\d{1,3}',line):
                    findings.append({'file':rel,'line':i,'text':line[:1500]})
        if p.name in ['version.json','version_copy.json']:
            versions[rel]=json.loads(p.read_text(encoding='utf-8-sig'))
    (out/'decoded_network_references.json').write_text(json.dumps(findings,ensure_ascii=False,indent=2),encoding='utf-8')
    info={'id':out.name,'hero_records':len(heroes),'heroes':heroes,'versions':versions,
          'lua_files':lua_count,'lua_non_bytecode_files':luatext_count,
          'network_reference_lines':len(findings),
          'hero_model_directories':[p.name for p in (d/'assets/data/model/heroes').iterdir() if p.is_dir()]}
    (out/'decoded_findings.json').write_text(json.dumps(info,ensure_ascii=False,indent=2),encoding='utf-8')
    summaries.append(info)
    print(json.dumps({k:v for k,v in info.items() if k!='hero_model_directories'},ensure_ascii=False),flush=True)
(ROOT/'decoded_findings.json').write_text(json.dumps(summaries,ensure_ascii=False,indent=2),encoding='utf-8')

font=ImageFont.truetype('C:/Windows/Fonts/msyh.ttc',25)
small=ImageFont.truetype('C:/Windows/Fonts/msyh.ttc',17)
sheet=Image.new('RGB',(960,310),(245,247,250));draw=ImageDraw.Draw(sheet)
for i,slug in enumerate(['moba_2016','ciyuan_2017','game300_2018']):
    a=json.loads((ROOT/slug/'summary.json').read_text(encoding='utf-8'))
    imgs=[]
    for icon in a['icons']:
        p=ROOT/slug/'unpacked'/icon['value']
        if p.is_file():
            try:imgs.append(Image.open(p).convert('RGBA'))
            except Exception:pass
    if imgs:
        im=max(imgs,key=lambda x:x.width*x.height);im.thumbnail((164,164))
        sheet.paste(im,(i*320+(320-im.width)//2,26),im)
    name=a['app_labels'][0]['value'];version=a['manifest']['android:versionName']
    draw.text((i*320+160,214),name,font=font,anchor='mm',fill=(25,35,55))
    draw.text((i*320+160,254),slug[-4:]+'  /  v'+version,font=small,anchor='mm',fill=(80,90,105))
sheet.save(ROOT/'icons_preview.png')
