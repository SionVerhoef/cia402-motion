"""Tests for scripts/check_vendor_index.py. Plain unittest, standard library only."""
import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(REPO, 'scripts'))

import check_vendor_index  # noqa: E402

README = """# Vendor deviations

| Page | Products |
|---|---|
{index}

## Porting between drives: where they differ

### Stopping

| | 0x605A | 0x605B |
|---|---|---|
{stop}

### Motion

| | Homing | Modes |
|---|---|---|
{motion}

## Adding a vendor
"""


def rows(*labels):
    return '\n'.join(f'| {label} | x | y |' for label in labels)


class VendorIndex(unittest.TestCase):

    def check(self, pages, index, stop, motion, readme=README):
        with tempfile.TemporaryDirectory() as d:
            for name in pages:
                with open(os.path.join(d, name), 'w', encoding='utf-8') as f:
                    f.write('# x\n')
            text = readme.format(index='\n'.join(f'| `{p}` | x |' for p in index),
                                 stop=rows(*stop), motion=rows(*motion))
            with open(os.path.join(d, 'README.md'), 'w', encoding='utf-8') as f:
                f.write(text)
            return [(n, m) for _, n, m in check_vendor_index.check(d)]

    def test_a_complete_readme_passes(self):
        self.assertEqual(self.check(['festo.md', 'stober.md'],
                                    ['festo.md', 'stober.md'],
                                    ['Festo CMMT', 'STOBER SC6 / SI6'],
                                    ['Festo CMMT', 'STOBER SC6 / SI6']), [])

    def test_one_page_may_have_several_porting_rows(self):
        self.assertEqual(self.check(['beckhoff.md'], ['beckhoff.md'],
                                    ['Beckhoff EL72x1', 'Beckhoff AX8000'],
                                    ['Beckhoff EL72x1']), [])

    def test_a_page_missing_from_the_index_fails(self):
        errors = self.check(['a.md', 'b.md'], ['a.md'], ['A', 'B'], ['A', 'B'])
        self.assertEqual([m for _, m in errors], ['b.md has no row in the index table'])

    def test_a_page_missing_from_one_porting_table_fails(self):
        errors = self.check(['a.md', 'b.md'], ['a.md', 'b.md'], ['A', 'B'], ['A'])
        self.assertEqual([m for _, m in errors],
                         ['b.md has no row in the porting table starting "Homing"'])

    def test_rows_without_a_page_fail_with_their_line(self):
        errors = self.check(['a.md'], ['a.md', 'gone.md'], ['A', 'Gone X'], ['A'])
        self.assertEqual(errors, [(6, 'index row gone.md: no such page'),
                                  (15, 'porting row "Gone X": no page gone.md')])

    def test_a_renamed_porting_section_fails_instead_of_passing(self):
        errors = self.check(['a.md'], ['a.md'], ['A'], ['A'],
                            readme=README.replace('## Porting', '## Moving'))
        self.assertEqual([m for _, m in errors],
                         ['no tables under "## Porting between drives"'])

    def test_the_repository_readme_lists_every_page(self):
        folder = os.path.join(REPO, check_vendor_index.VENDORS)
        self.assertEqual(check_vendor_index.check(folder), [])


if __name__ == '__main__':
    unittest.main()
