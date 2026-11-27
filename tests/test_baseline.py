"""Tests for baseline.py: the bench-test.md section 4 baseline traces as that section says."""
import csv
import io
import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), 'scripts'))
sys.path.insert(0, HERE)

import baseline  # noqa: E402
import cia402  # noqa: E402

# Scenarios whose recording shows Fault or Fault reaction active: trace notes 'read 0x603F'.
FAULTED = (6, 7, 8, 12)


def traced(rows):
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(baseline.COLUMNS)
    w.writerows(rows)
    samples, columns = cia402.read_trace(buf.getvalue().splitlines())
    return cia402.trace(samples, columns)


class Baseline(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.runs = {lag: baseline.run(lag) for lag in (1, 3)}

    def test_every_scenario_is_recorded(self):
        for lag, run in self.runs.items():
            self.assertEqual(sorted(run), list(range(1, 13)))

    def test_trace_finds_no_error_or_warning_and_a_note_for_each_fault(self):
        for lag, run in self.runs.items():
            for number, rows in run.items():
                with self.subTest(lag=lag, scenario=number):
                    r = traced(rows)
                    self.assertEqual(r['counts']['error'], 0, r['findings'])
                    self.assertEqual(r['counts']['warning'], 0, r['findings'])
                    self.assertEqual(r['counts']['note'], int(number in FAULTED),
                                     r['findings'])

    def test_way_down_sends_0x0000_once_switch_on_disabled_shows(self):
        # bench-test.md, row 3: no tStateTimeout (2 s) wait when the drive gets there.
        for lag, run in self.runs.items():
            with self.subTest(lag=lag):
                rows = run[3]
                sod = next(i for i, row in enumerate(rows) if row[2] & 0x4F == 0x40)
                zero = next(i for i, row in enumerate(rows) if row[1] == 0x0000)
                self.assertLess(zero - sod, 5)

    def test_main_writes_one_file_per_scenario(self):
        with tempfile.TemporaryDirectory() as out:
            with open(os.devnull, 'w') as null:
                stdout, sys.stdout = sys.stdout, null
                try:
                    baseline.main([out])
                finally:
                    sys.stdout = stdout
            names = sorted(os.listdir(out))
            self.assertEqual(len(names), 12)
            samples, _ = cia402.read_trace(
                open(os.path.join(out, 'scenario_2.csv'), encoding='utf-8').read().splitlines())
            self.assertTrue(samples)


if __name__ == '__main__':
    unittest.main()
