from pathlib import Path
import struct, sys, json
from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB, CS_MODE_ARM

def inspect_elf(path,match):
    b=path.read_bytes()
    assert b[:5]==b'\x7fELF\x01'
    def u16(p):return struct.unpack_from('<H',b,p)[0]
    def u32(p):return struct.unpack_from('<I',b,p)[0]
    off=u32(32);sz=u16(46);count=u16(48)
    sections=[struct.unpack_from('<10I',b,off+i*sz) for i in range(count)]
    symbols={};matches=[]
    for s in sections:
        if s[1] not in (2,11):continue
        st=sections[s[6]];pool=b[st[4]:st[4]+st[5]]
        for p in range(s[4],s[4]+s[5],s[9]):
            n,v,size,info,other,sec=struct.unpack_from('<IIIBBH',b,p)
            end=pool.find(b'\0',n);name=pool[n:end].decode('ascii','replace')
            if v:symbols[v&~1]=name
            if match in name and size:matches.append((name,v,size,sec))
    out=[]
    for name,v,size,sec in matches:
        s=sections[sec];fileoff=(v&~1)-s[3]+s[4]
        out.append(f'\n{name} vaddr={v:#x} size={size}')
        md=Cs(CS_ARCH_ARM,CS_MODE_THUMB if v&1 else CS_MODE_ARM)
        for i in md.disasm(b[fileoff:fileoff+size],v&~1):
            annotation=''
            if i.mnemonic in ('bl','b','blx') and i.op_str.startswith('#'):
                annotation=symbols.get(int(i.op_str[1:],0),'')
            out.append(f'{i.address:08x}  {i.mnemonic:8} {i.op_str} {annotation}')
    return '\n'.join(out)
if __name__=='__main__':
    root=Path(__file__).resolve().parent
    slug=sys.argv[1] if len(sys.argv)>1 else 'ciyuan_2017'
    match=sys.argv[2] if len(sys.argv)>2 else 'checkFileCompress'
    p=next(iter((root/slug/'unpacked/lib').rglob('libgame.so')),None) or next((root/slug/'unpacked/lib').rglob('libtombird.so'))
    result=inspect_elf(p,match)
    (root/slug/(match+'.disasm.txt')).write_text(result,encoding='utf-8')
    print(result)
