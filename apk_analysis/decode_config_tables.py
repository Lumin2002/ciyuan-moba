"""Decode ciyuan_2017 *_c.dat protobuf config tables using the schema recovered
from the client binary (proto_schema_recovered.json).

The .dat tables are protobuf messages; field names come from the recovered
k*FieldNumber constants, and the wire type in the data gives the actual type
(wire 0 = varint, 1 = fixed64/double, 2 = length-delimited, 5 = fixed32/float).
So one can decode the tables without ever having a .proto.

Read-only: prints summaries; writes JSON/CSV only when asked.
"""
from pathlib import Path
import struct, json, sys, csv

ROOT = Path(__file__).resolve().parent
SLUG = 'ciyuan_2017'


def conf_dir(slug=SLUG):
    """Directory holding the decoded protobuf config tables for a package."""
    return ROOT / slug / 'decoded' / 'assets' / 'data' / 'conf'


CONF = conf_dir(SLUG)  # default package, kept for convenience


def varint(b, p):
    v = s = 0
    while True:
        x = b[p]; p += 1
        v |= (x & 127) << s
        if not x & 128:
            return v, p
        s += 7
        if s > 70:
            raise ValueError('bad varint')


def parse_fields(b):
    """Return [(field, wire, value)]; value is int for wire 0, bytes otherwise."""
    p, out = 0, []
    while p < len(b):
        tag, p = varint(b, p)
        field, wire = tag >> 3, tag & 7
        if field == 0:
            raise ValueError('field 0')
        if wire == 0:
            v, p = varint(b, p)
        elif wire == 1:
            v = b[p:p + 8]; p += 8
        elif wire == 2:
            n, p = varint(b, p)
            v = b[p:p + n]; p += n
        elif wire == 5:
            v = b[p:p + 4]; p += 4
        else:
            raise ValueError(f'wire {wire}')
        if p > len(b):
            raise ValueError('truncated')
        out.append((field, wire, v))
    return out


def typed(name, wire, value):
    """Best-effort typed value using the field-name prefix convention."""
    if wire == 0:
        # 'N'/'U' prefixes are integer-ish; a varint of 0/1 with an 'N' name is
        # far more likely a bool than a number, but we keep the raw int too.
        return value
    if wire == 5:
        f = struct.unpack('<f', value)[0]
        return f if name[:1].upper() == 'F' else f
    if wire == 1:
        return struct.unpack('<d', value)[0]
    if wire == 2:
        try:
            return value.decode('utf-8')
        except UnicodeDecodeError:
            pass
        try:
            return value.decode('gb18030')
        except UnicodeDecodeError:
            return {'__bytes__': value.hex()}
    return value


def cell_text(v):
    if isinstance(v, float):
        return f'{v:.6g}'
    if isinstance(v, dict):
        return '<bytes ' + str(len(v['__bytes__']) // 2) + 'B>'
    return str(v)


def load_schema(slug=SLUG):
    d = json.loads((ROOT / slug / 'proto_schema_recovered.json').read_text(encoding='utf-8'))
    return {msg: {int(n): name for name, n in fields.items()}
            for msg, fields in d['messages'].items()}


def norm(s):
    """Normalise a message name or file stem: drop the 'S' prefix, case, underscores.

    SSkill_SkillLevel -> skillskilllevel,  skill_skilllevel -> skillskilllevel
    """
    n = s.lower().replace('_', '')
    return n[1:] if n.startswith('s') else n


def resolve_messages(path, schema):
    """Map xxx_c.dat -> (pool_msg, element_msg).

    Tables are stored as a pool message holding `repeated Element data = 1`,
    e.g. SSkill_SkillLevelDataPool -> SSkill_SkillLevel. The element carries the
    real field names, so it must be used to name each record's fields.

    File stems do not always equal the message name (growupgeniustable_c.dat ->
    SGrowUpGenius, monsterdata_c.dat -> SExcelMonster), so candidates are scored:
    exact normalised match first, then longest common prefix / containment, then
    the shortest name.
    """
    stem = norm(path.stem.replace('_c', ''))

    def common_prefix(a, b):
        n = 0
        while n < min(len(a), len(b)) and a[n] == b[n]:
            n += 1
        return n

    def contained(a, b):
        if b and b in a:
            return len(b)
        if a and a in b:
            return len(a)
        return 0

    def score_for(element, raw):
        m = norm(element)
        exact = (m == stem)
        measure = max(common_prefix(m, stem), contained(m, stem),
                      contained(norm(raw), stem))
        return (0 if exact else 1, -measure, len(m))

    best = None
    for raw in schema:
        if raw.endswith('DataPool') or raw.endswith('Pool'):
            element = raw[:-8] if raw.endswith('DataPool') else raw[:-4]
            if element not in schema:
                element = raw
        else:
            element = raw
        key = score_for(element, raw)
        if best is None or key < best[0]:
            best = (key, element, raw)

    if best is None:
        return None, None
    key, element, raw = best
    if key[0] != 0 and key[1] > -5:
        return None, None
    pool = raw if raw.endswith('Pool') else element
    return pool, element


def decode_pool(path, schema, element_msg):
    """Decode a table into [ {field_name: value} ] using the element message."""
    top = parse_fields(path.read_bytes())
    records = [v for field, wire, v in top if wire == 2]
    out = []
    for rec in records:
        row = {}
        for field, wire, value in parse_fields(rec):
            name = schema.get(element_msg, {}).get(field, f'f{field}')
            row[name] = typed(name, wire, value)
        out.append(row)
    return out


if __name__ == '__main__':
    argv = sys.argv[1:]
    slug = SLUG
    if argv and argv[0].startswith('--slug='):
        slug = argv[0].split('=', 1)[1]
        argv = argv[1:]
    schema = load_schema(slug)
    conf = conf_dir(slug)
    targets = argv or ['logic', 'skill_skilllevel', 'skill_skillbase']
    for stem in targets:
        path = conf / f'{stem}_c.dat'
        if not path.is_file():
            print(f'{stem}: MISSING'); continue
        pool, element = resolve_messages(path, schema)
        print(f'=== [{slug}] {path.name}  ({path.stat().st_size:,} bytes)'
              f'  -> pool={pool}  element={element}'
              f'  ({len(schema.get(element, {}))} known fields) ===')
        rows = decode_pool(path, schema, element)
        print(f'    {len(rows)} records')
        if rows:
            print(f'    fields: {", ".join(sorted(rows[0].keys()))}')
            for r in rows[:3]:
                print('    ' + ' | '.join(f'{k}={cell_text(v)}' for k, v in
                                          list(r.items())[:16]))
        print()
