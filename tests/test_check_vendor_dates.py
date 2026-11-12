"""Tests for scripts/check_vendor_dates.py. Plain unittest, standard library only."""
import datetime
import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(REPO, 'scripts'))

import check_vendor_dates  # noqa: E402

TODAY = datetime.date(2027, 6, 1)


class VendorDates(unittest.TestCase):

    def check(self, pages):
        with tempfile.TemporaryDirectory() as d:
            for name, text in pages.items():
                with open(os.path.join(d, name), 'w', encoding='utf-8') as f:
                    f.write(text)
            errors, warnings = check_vendor_dates.check(d, TODAY)
        strip = lambda found: [(os.path.basename(p), n, m) for p, n, m in found]
        return strip(errors), strip(warnings)

    def test_a_recent_read_passes(self):
        self.assertEqual(self.check({'a.md': '# A\n\n**Read 2027-01-02**: manual\n'}),
                         ([], []))

    def test_a_page_without_a_read_line_fails(self):
        errors, _ = self.check({'a.md': '# A\n\nRead 2027-01-02, not bold.\n'})
        self.assertEqual([(e[0], e[1]) for e in errors], [('a.md', 1)])

    def test_the_readme_is_not_a_vendor_page(self):
        self.assertEqual(self.check({'README.md': '# Vendors\n'}), ([], []))

    def test_each_old_read_warns_with_its_line(self):
        errors, warnings = self.check({'a.md': '**Read 2026-05-31**: x\n\n'
                                               '**Read 2026-06-01**: y\n\n'
                                               '**Read 2027-05-01**: z\n'})
        self.assertEqual(errors, [])
        self.assertEqual([(w[0], w[1]) for w in warnings], [('a.md', 1)])
        self.assertIn('366 days', warnings[0][2])

    def test_a_bad_or_future_date_fails(self):
        errors, _ = self.check({'a.md': '**Read 2027-02-30**: x\n**Read 2027-06-02**: y\n'})
        self.assertEqual([e[1] for e in errors], [1, 2])

    def test_the_repository_pages_all_have_a_read_line(self):
        folder = os.path.join(REPO, check_vendor_dates.VENDORS)
        errors, _ = check_vendor_dates.check(folder, datetime.date.today())
        self.assertEqual(errors, [])


if __name__ == '__main__':
    unittest.main()
