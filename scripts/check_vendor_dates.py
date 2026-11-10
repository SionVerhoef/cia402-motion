#!/usr/bin/env python3
"""Check that every vendor page says when its sources were read, and warn when that is old.

Each references/vendors/<vendor>.md opens a source block with a bold line such as
**Read 2026-11-08**: <document>. A page without one fails: a vendor fact needs a source and
a date (SKILL.md, rule 3). A read date more than a year old is only a warning, printed as a
GitHub annotation: drives get new firmware and manuals new editions, so the page is due a
re-read, but it is not wrong yet. Run from the repository root.
"""
import argparse
import datetime
import os
import re
import sys

VENDORS = os.path.join('references', 'vendors')
READ = re.compile(r'\*\*Read (\d{4}-\d{2}-\d{2})\*\*')
MAX_AGE = datetime.timedelta(days=365)


def check(folder, today):
    """(errors, warnings), each a list of (path, line, message)."""
    errors, warnings = [], []
    for name in sorted(os.listdir(folder)):
        if not name.endswith('.md') or name == 'README.md':
            continue  # the README is the index, not a vendor page
        path = os.path.join(folder, name)
        with open(path, encoding='utf-8') as f:
            lines = f.readlines()
        dates = [(n, m.group(1)) for n, line in enumerate(lines, 1)
                 for m in READ.finditer(line)]
        if not dates:
            errors.append((path, 1, 'no "**Read YYYY-MM-DD**" line: say when the source '
                                    'was read'))
        for n, text in dates:
            try:
                read = datetime.date.fromisoformat(text)
            except ValueError:
                errors.append((path, n, f'{text} is not a date'))
                continue
            if read > today:
                errors.append((path, n, f'read {text}, which is in the future'))
            elif today - read > MAX_AGE:
                warnings.append((path, n, f'source read {text}, {(today - read).days} days '
                                          f'ago: due a re-read against the current edition'))
    return errors, warnings


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--today', type=datetime.date.fromisoformat,
                        default=datetime.date.today(), help='YYYY-MM-DD (default: today)')
    args = parser.parse_args(argv)
    errors, warnings = check(VENDORS, args.today)
    for path, line, message in warnings:
        print(f'::warning file={path},line={line}::{message}')
    for path, line, message in errors:
        print(f'::error file={path},line={line}::{message}')
    print(f'{len(errors)} error(s), {len(warnings)} stale source(s) in {VENDORS}')
    return 1 if errors else 0


if __name__ == '__main__':
    sys.exit(main())
