#!/usr/bin/env python3
"""Check that every vendor page has a row in the vendor index and in each porting table.

references/vendors/README.md lists every page twice over: once in the index table, whose
first column is the file name in backticks (`festo.md`), and once in each table under
"## Porting between drives", whose first column starts with the vendor name (Festo CMMT).
A porting row belongs to the page named by its first word, lowercased: "STOBER SC6 / SI6"
is stober.md. Vendor pages are added in parallel and the README is edited by hand, so a
page can land without its rows, or a row can outlive its page. Both fail. Run from the
repository root.
"""
import os
import re
import sys

VENDORS = os.path.join('references', 'vendors')
INDEX_PAGE = re.compile(r'^`([^`]+\.md)`$')


def cells(row):
    """The cells of a Markdown table row, stripped: '| | a |' is ['', 'a']."""
    return [c.strip() for c in row.strip()[1:-1].split('|')]


def tables(lines):
    """[(h2 heading, header row, [(line number, first cell)])], one entry per table."""
    found, heading, rows = [], '', None
    for n, line in enumerate(lines, 1):
        if line.startswith('## '):
            heading = line[3:].strip()
        if line.startswith('|'):
            if rows is None:  # header row; the separator row follows it
                rows = []
                found.append((heading, line, rows))
            elif not re.match(r'^\|[\s|:-]+\|$', line.strip()):
                rows.append((n, cells(line)[0]))
        else:
            rows = None
    return found


def check(folder):
    """A list of (path, line, message)."""
    readme = os.path.join(folder, 'README.md')
    pages = sorted(name for name in os.listdir(folder)
                   if name.endswith('.md') and name != 'README.md')
    with open(readme, encoding='utf-8') as f:
        found = tables(f.read().splitlines())
    index = [rows for _, header, rows in found
             if cells(header)[0] == 'Page']
    porting = [(header, rows) for heading, header, rows in found
               if heading.startswith('Porting')]
    errors = []
    if len(index) != 1:
        errors.append((readme, 1, f'expected one "| Page | ... |" index table, found '
                                  f'{len(index)}'))
    if not porting:
        errors.append((readme, 1, 'no tables under "## Porting between drives"'))
    for rows in index[:1]:
        listed = {}
        for n, cell in rows:
            m = INDEX_PAGE.match(cell)
            if not m:
                errors.append((readme, n, f'index row "{cell}" is not a `page.md` name'))
            elif m.group(1) not in pages:
                errors.append((readme, n, f'index row {m.group(1)}: no such page'))
            else:
                listed.setdefault(m.group(1), n)
        for page in pages:
            if page not in listed:
                errors.append((readme, 1, f'{page} has no row in the index table'))
    for header, rows in porting:
        line = next((n for n, _ in rows), 1)
        covered = set()
        for n, cell in rows:
            page = (cell.split() or [''])[0].lower() + '.md'
            if page in pages:
                covered.add(page)
            else:
                errors.append((readme, n, f'porting row "{cell}": no page {page}'))
        title = cells(header)[1]
        for page in pages:
            if page not in covered:
                errors.append((readme, line, f'{page} has no row in the porting table '
                                             f'starting "{title}"'))
    return errors


def main():
    errors = check(VENDORS)
    for path, line, message in errors:
        print(f'::error file={path},line={line}::{message}')
    print(f'{len(errors)} error(s) in {os.path.join(VENDORS, "README.md")}')
    return 1 if errors else 0


if __name__ == '__main__':
    sys.exit(main())
