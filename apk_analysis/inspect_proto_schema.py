"""Recover protobuf field numbers from the native core library's k*FieldNumber constants.

protobuf generates a `static const int kFooFieldNumber = N;` for every field and
keeps the symbol in the .so. Those constants are exactly the wire/schema numbers,
so the client binary alone documents the schema of every config table and battle
message it knows about - including tables whose .proto was never shipped.

Read-only: parses the ELF symbol table and prints/records the recovered schema.
"""
from pathlib import Path
import struct, re, json, sys

ROOT = Path(__file__).resolve().parent


def elf_symbols(path):
    """Yield (vaddr, size, name) for every symbol, plus a vaddr->file-offset mapper."""
    b = path.read_bytes()
    if b[:5] != b'\x7fELF\x01':
        raise ValueError('not a 32-bit ELF: ' + str(path))
    shoff, = struct.unpack_from('<I', b, 32)
    shentsize, shnum = struct.unpack_from('<HH', b, 46)

    sections = []
    for i in range(shnum):
        s = struct.unpack_from('<10I', b, shoff + i * shentsize)
        sections.append({'name': s[0], 'type': s[1], 'flags': s[2], 'addr': s[3],
                         'offset': s[4], 'size': s[5], 'link': s[6],
                         'entsize': s[9]})

    def resolve(addr, count):
        for s in sections:
            if s['type'] != 8 and s['addr'] <= addr < s['addr'] + s['size']:
                off = addr - s['addr'] + s['offset']
                return b[off:off + count]
        return None

    syms = []
    for s in sections:
        if s['type'] not in (2, 11) or not s['entsize']:
            continue
        strtab = sections[s['link']]
        pool = b[strtab['offset']:strtab['offset'] + strtab['size']]
        for p in range(s['offset'], s['offset'] + s['size'], s['entsize']):
            nameoff, value, size, info, other, shndx = struct.unpack_from('<IIIBBH', b, p)
            end = pool.find(b'\0', nameoff)
            name = pool[nameoff:end].decode('ascii', 'replace')
            if name:
                syms.append((value, size, name))
    return syms, resolve


def demangle_member(mangled):
    """Recover ClassName + member name from an Itanium-mangled _ZN...E symbol.

    Handles the common nested form (_ZN13GameDuplicate23OnMsgPlayerEnterMySightEP3Msg)
    as well as a trailing namespace. Returns (scope, member) or None.
    """
    if not mangled.startswith('_ZN'):
        return None
    i, parts = 3, []
    while i < len(mangled):
        if mangled[i] == 'E':
            break
        j = i
        while j < len(mangled) and mangled[j].isdigit():
            j += 1
        if j == i:
            break
        n = int(mangled[i:j])
        parts.append(mangled[j:j + n])
        i = j + n
    if not parts:
        return None
    return '::'.join(parts[:-1]), parts[-1]


def recover_field_numbers(slug):
    lib = ROOT / slug / 'unpacked' / 'lib' / 'armeabi' / 'libgame.so'
    if not lib.is_file():
        lib = next((ROOT / slug / 'unpacked' / 'lib').rglob('libgame.so'), None)
    if lib is None:
        lib = next((ROOT / slug / 'unpacked' / 'lib').rglob('libtombird.so'))
    syms, resolve = elf_symbols(lib)

    schema, unresolved = {}, []
    for vaddr, size, name in syms:
        if not name.endswith('FieldNumberE') or 'k' not in name:
            continue
        parsed = demangle_member(name)
        if not parsed:
            continue
        scope, member = parsed
        m = re.fullmatch(r'k(.+)FieldNumber', member)
        if not m:
            continue
        raw = resolve(vaddr, 4)
        if raw is None or len(raw) < 4:
            unresolved.append(name)
            continue
        schema.setdefault(scope, {})[m.group(1)] = struct.unpack('<i', raw)[0]

    out = {'lib': lib.relative_to(ROOT).as_posix(), 'message_count': len(schema),
           'field_count': sum(len(v) for v in schema.values()),
           'unresolved': unresolved, 'messages': schema}
    return out


def parse_proto_dir(slug):
    """Parse the 2018 .proto files into {message: {field: number}} for cross-checking."""
    conf = ROOT / slug / 'decoded' / 'assets' / 'data' / 'conf'
    result = {}
    for p in sorted(conf.glob('*.proto')):
        text = p.read_text(encoding='utf-8', errors='replace')
        for block in re.finditer(r'message\s+(\w+)\s*\{(.*?)\n\}', text, re.S):
            msg, body = block.group(1), block.group(2)
            fields = {}
            for f in re.finditer(r'=\s*(\d+)\s*;', body):
                line_start = body.rfind('\n', 0, f.start()) + 1
                decl = body[line_start:f.start()]
                m = re.search(r'(\w+)\s*$', decl)
                if m:
                    fields[m.group(1)] = int(f.group(1))
            if fields:
                result[msg] = fields
    return result


if __name__ == '__main__':
    slug = sys.argv[1] if len(sys.argv) > 1 else 'ciyuan_2017'
    recovered = recover_field_numbers(slug)
    (ROOT / slug / 'proto_schema_recovered.json').write_text(
        json.dumps(recovered, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f"{slug}: lib={recovered['lib']}")
    print(f"  recovered {recovered['field_count']} field numbers "
          f"across {recovered['message_count']} messages, "
          f"{len(recovered['unresolved'])} unresolved")

    reference = parse_proto_dir('game300_2018')
    if reference:
        # protobuf emits `kUAttackFieldNumber` for a proto field named `uAttack`,
        # so field names are compared case-insensitively.
        ref_ci = {msg: {k.lower(): (k, v) for k, v in fields.items()}
                  for msg, fields in reference.items()}
        both = sorted(set(recovered['messages']) & set(reference))
        agree = disagree = only_client = 0
        diffs = []
        for msg in both:
            for field, num in recovered['messages'][msg].items():
                hit = ref_ci[msg].get(field.lower())
                if hit is None:
                    only_client += 1
                elif hit[1] == num:
                    agree += 1
                else:
                    disagree += 1
                    diffs.append({'message': msg, 'field_this_package': field,
                                  'field_2018': hit[0],
                                  'this_package': num, 'game300_2018': hit[1]})
        print(f"\n  cross-check vs game300_2018 .proto "
              f"({len(both)} shared messages, field names compared case-insensitively)")
        print(f"    agree={agree}  disagree={disagree}  only-in-{slug}={only_client}")
        for d in diffs[:30]:
            print(f"    DIFF {d['message']}.{d['field_this_package']} vs {d['field_2018']}: "
                  f"{slug}={d['this_package']} 2018={d['game300_2018']}")
        (ROOT / f'proto_schema_crosscheck_{slug}.json').write_text(json.dumps(
            {'slug': slug, 'shared_messages': len(both), 'agree': agree,
             'disagree': disagree, 'only_in_this_package': only_client,
             'differences': diffs},
            ensure_ascii=False, indent=2), encoding='utf-8')
