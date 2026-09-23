"""Recover the attribute-ID vocabulary and inventory the damage-relevant inputs
available in the ciyuan_2017 client config.

Two independent label sources name the same attribute IDs:
  * SGrowUpGenius.SAttribute = "id;value"  paired with SDescription ("物理攻击+1")
  * SRuneMapData.Unattrtype paired with Stips ("物理攻击")
Matching them against each other is what makes the IDs readable without any
client-side enum in the binary.

This script also measures which damage-formula fields are *populated* in the
shipped skill data, which is the evidence for where the damage model lives.

Read-only: writes attribute_enum.json / damage_inputs.json for the report.
"""
from pathlib import Path
import re, json, collections, sys

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
import decode_config_tables as D  # noqa: E402

SLUG = 'ciyuan_2017'
schema = D.load_schema(SLUG)


def strip_value(text):
    """'物理攻击+1' / '攻击速度+3%' -> '物理攻击' / '攻击速度'."""
    return re.sub(r'[+\-]?\d+(?:\.\d+)?\s*%?$', '', str(text)).strip()


def recover_enum():
    enum = collections.defaultdict(lambda: collections.defaultdict(set))

    rows = D.decode_pool(D.CONF / 'growupgeniustable_c.dat', schema, 'SGrowUpGenius')
    for r in rows:
        m = re.match(r'(\d+);', str(r.get('SAttribute', '')))
        if m:
            name = strip_value(r.get('SDescription', ''))
            if name:
                enum[int(m.group(1))]['genius'].add(name)

    runes = D.decode_pool(D.CONF / 'runemapdata_c.dat', schema, 'SRuneMapData')
    for r in runes:
        t, tip = r.get('Unattrtype'), str(r.get('Stips', '') or '')
        if isinstance(t, int) and tip:
            enum[t]['rune'].add(tip)

    return enum, rows, runes


def fight_value_weights(runes):
    """Unfightvalue is the game's own per-attribute valuation of a rune."""
    w = collections.defaultdict(lambda: collections.defaultdict(list))
    for r in runes:
        t, v, fv, q = (r.get('Unattrtype'), r.get('Fattrvalue'),
                       r.get('Unfightvalue'), r.get('Unquality'))
        if isinstance(t, int) and isinstance(v, (int, float)) and isinstance(fv, (int, float)) and v:
            w[t][q].append(round(fv / v, 4))
    return {t: {str(q): sorted(set(vals)) for q, vals in byq.items()}
            for t, byq in w.items()}


def damage_field_audit():
    """Which damage-formula fields exist in the schema vs in the shipped data."""
    rows = D.decode_pool(D.CONF / 'skill_skilllevel_c.dat', schema, 'SSkill_SkillLevel')
    present = collections.Counter()
    for r in rows:
        for k in r:
            present[k] += 1
    known = schema['SSkill_SkillLevel']
    watched = ['NFormulaID', 'NGodFormulaID', 'NDamageCoefficientFirst',
               'NDamageCoefficientFirstSecond', 'NDamageCoefficientFirstS',
               'NAttackRate', 'NHitAddons', 'NIfKeepAttack', 'NDamageType',
               'NCombineDamage', 'NTargetHurtActRate']
    audit = {}
    for name in watched:
        field = next((f for f, n in known.items() if n == name), None)
        audit[name] = {
            'declared_in_client_schema_at': field,
            'records_containing_it': present.get(name, 0),
            'of_total_records': len(rows),
        }
    # zero-values are serialised explicitly, so absence really means "not set"
    audit['_zero_value_check'] = {
        'records_with_NCostMP_present_and_zero': sum(
            1 for r in rows if r.get('NCostMP') == 0),
        'note': 'explicit zeros are written, so a missing field is genuinely unset',
    }
    return audit, len(rows)


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    enum, genius, runes = recover_enum()

    # Which human labels are attached to more than one attribute ID? Those are
    # genuine ambiguities in the ID space and must not be silently merged.
    label_ids = collections.defaultdict(set)
    for aid, vals in enum.items():
        for names in vals.values():
            for n in names:
                label_ids[n].add(aid)
    ambiguous = {n: sorted(ids) for n, ids in sorted(label_ids.items()) if len(ids) > 1}

    out_enum = {
        'source': 'SGrowUpGenius.SDescription + SRuneMapData.Stips',
        'attribute_count': len(enum),
        'attributes': {
            str(k): {src: sorted(v) for src, v in sorted(vals.items())}
            for k, vals in sorted(enum.items())
        },
        'labels_spanning_multiple_ids': ambiguous,
    }
    (ROOT / SLUG / 'attribute_enum.json').write_text(
        json.dumps(out_enum, ensure_ascii=False, indent=2), encoding='utf-8')

    audit, total = damage_field_audit()
    (ROOT / SLUG / 'damage_inputs.json').write_text(json.dumps(
        {'skill_level_records': total, 'field_audit': audit,
         'fight_value_weights_by_quality': fight_value_weights(runes)},
        ensure_ascii=False, indent=2), encoding='utf-8')

    print(f'attribute IDs recovered: {out_enum["attribute_count"]}')
    for k, v in out_enum['attributes'].items():
        label = ' | '.join(f'{s}:{"/".join(n)}' for s, n in v.items())
        print(f'  {k:>3}  {label}')
    print('\nlabels tied to more than one ID:')
    for n, ids in ambiguous.items():
        print(f'  {n}: {ids}')
    print(f'\nskill_skilllevel records: {total}')
    print('damage-formula field audit:')
    for name, a in audit.items():
        if name.startswith('_'):
            continue
        print(f'  {name:<32} schema field={str(a["declared_in_client_schema_at"]):>4}'
              f'  populated in {a["records_containing_it"]}/{a["of_total_records"]}')
    print(f'  zero-value check: {audit["_zero_value_check"]}')
