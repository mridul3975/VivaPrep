"""Verify frozen bytes, distinguishing Git's LF/CRLF conversion from code changes."""
import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def frozen_bytes(path, expected):
    if not path.is_file():
        return None
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() == expected:
        return raw
    # Accept only a candidate whose bytes exactly match the pre-run hash.
    # Nothing resembling a semantic or whitespace-insensitive source comparison.
    lf = raw.replace(b'\r\n', b'\n')
    for candidate in (lf, lf.replace(b'\n', b'\r\n')):
        if hashlib.sha256(candidate).hexdigest() == expected:
            return candidate
    return None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--restore-line-endings', action='store_true', help='Restore only exact frozen LF/CRLF bytes so the original strict runner can be replicated on another platform')
    args = parser.parse_args()
    manifest = json.loads((HERE / 'freeze.json').read_text())
    mismatches, converted = [], []
    for name, expected in manifest['files'].items():
        path = (HERE.parent / name).resolve()
        if HERE.parent not in path.parents:
            raise SystemExit('Unsafe manifest path')
        candidate = frozen_bytes(path, expected)
        if candidate is None:
            mismatches.append(name)
        elif candidate != path.read_bytes():
            converted.append(name)
    if mismatches:
        raise SystemExit('Changed frozen content; do not reuse this version: ' + ', '.join(mismatches))
    if args.restore_line_endings:
        for name in converted:
            path = HERE.parent / name
            path.write_bytes(frozen_bytes(path, manifest['files'][name]))
    print(f'Frozen content verified; newline-only differences: {len(converted)}' + (' (restored to exact pre-run bytes).' if args.restore_line_endings else '.'))


if __name__ == '__main__':
    main()
