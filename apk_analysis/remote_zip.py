"""Read a remote ZIP over HTTP Range requests without downloading the whole archive.

A ZIP's central directory sits at the end of the file and lists every entry with
its local-header offset and sizes. Fetching the tail, then the directory, then
only the byte ranges of the entries we care about, keeps a 1.4 GB archive down to
a few hundred kilobytes of traffic.

Byte ranges are fetched with curl rather than urllib: Python's urllib returned an
empty body when going through the local HTTPS proxy, while curl's Range requests
worked reliably (206 + correct Content-Length).

Usage:
    python remote_zip.py list  <url> <size> [substring] [--proxy URL]
    python remote_zip.py fetch <url> <size> <outdir> [substring] [--proxy URL]
"""
from pathlib import Path
import argparse, struct, subprocess, zlib

CHUNK_TAIL = 4 << 20          # search this much of the tail for the EOCD


def make_getter(url, proxy=None, timeout=180):
    def get(start, end):
        cmd = ['curl.exe', '-sS', '-m', str(timeout), '-r', f'{start}-{end}']
        if proxy:
            cmd += ['--proxy', proxy]
        cmd.append(url)
        r = subprocess.run(cmd, capture_output=True)
        if r.returncode != 0:
            raise RuntimeError(f'curl failed ({r.returncode}) for {start}-{end}: '
                               + r.stderr.decode('utf-8', 'replace')[:200])
        return r.stdout
    return get


def find_eocd(get, size):
    """Locate the End Of Central Directory record and return its fields."""
    tail = get(max(0, size - CHUNK_TAIL), size - 1)
    i = tail.rfind(b'PK\x05\x06')
    while i >= 0:
        if i + 22 <= len(tail):
            (_disk, _cddisk, _n_disk, n_total, cd_size, cd_off, _clen) = \
                struct.unpack_from('<HHHHIIH', tail, i + 4)
            if cd_off + cd_size <= size:
                return n_total, cd_size, cd_off
        i = tail.rfind(b'PK\x05\x06', 0, i)
    raise SystemExit('EOCD not found in the tail; the file may be truncated '
                     'or use ZIP64')


def read_central_directory(get, cd_off, cd_size):
    """Yield {name, method, comp_size, uncomp_size, local_off} per entry."""
    data = get(cd_off, cd_off + cd_size - 1)
    p, out = 0, []
    while p + 46 <= len(data) and data[p:p + 4] == b'PK\x01\x02':
        method, = struct.unpack_from('<H', data, p + 10)
        comp, uncomp = struct.unpack_from('<II', data, p + 20)
        nlen, elen, clen = struct.unpack_from('<HHH', data, p + 28)
        local_off, = struct.unpack_from('<I', data, p + 42)
        name = data[p + 46:p + 46 + nlen].decode('utf-8', 'replace')
        out.append({'name': name, 'method': method, 'comp_size': comp,
                    'uncomp_size': uncomp, 'local_off': local_off})
        p += 46 + nlen + elen + clen
    return out


def extract(get, entry):
    """Fetch one entry's bytes and inflate it."""
    head = get(entry['local_off'], entry['local_off'] + 29)
    if head[:4] != b'PK\x03\x04':
        raise ValueError('bad local header')
    nlen, elen = struct.unpack_from('<HH', head, 26)
    start = entry['local_off'] + 30 + nlen + elen
    raw = get(start, start + entry['comp_size'] - 1)
    if entry['method'] == 0:
        return raw
    if entry['method'] == 8:
        return zlib.decompress(raw, -15)
    raise ValueError(f"unsupported method {entry['method']}")


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('cmd', choices=['list', 'fetch'])
    ap.add_argument('url')
    ap.add_argument('size', type=int)
    ap.add_argument('outdir', nargs='?', default='_downloads/zipout')
    ap.add_argument('--match', default='')
    ap.add_argument('--proxy', default=None)
    ap.add_argument('--limit', type=int, default=120)
    a = ap.parse_args()

    get = make_getter(a.url, proxy=a.proxy)
    n_total, cd_size, cd_off = find_eocd(get, a.size)
    print(f'EOCD: total entries={n_total} cd_size={cd_size:,} cd_offset={cd_off:,}')
    entries = read_central_directory(get, cd_off, cd_size)
    print(f'parsed {len(entries)} entries')

    hits = [e for e in entries if a.match.lower() in e['name'].lower()]
    print(f'matching "{a.match}": {len(hits)}')
    for e in hits[:a.limit]:
        print(f"   {e['uncomp_size']:>10,}  {e['name']}")

    if a.cmd == 'fetch':
        outdir = Path(a.outdir)
        for e in hits:
            dest = outdir / e['name']
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(extract(get, e))
            print('saved', dest)
