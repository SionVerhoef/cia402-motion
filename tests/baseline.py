"""The baseline of templates/bench-test.md, section 4: the section 5 scenarios run against the
simulated drive of test_templates.py and written out as CSV in the layout of a TwinCAT Scope
export, one file per scenario, for `cia402.py trace` and for comparing with the bench.

    python3 tests/baseline.py OUT_DIR [--lag N]

One FB instance runs the scenarios in order, as on the bench, with the default
ST_Cia402Config. The statusword reaches the FB `lag` cycles late (default 1, as on EtherCAT).
Each row is one task cycle: the drive's inputs as the FB read them, and what it wrote. In 12
the inputs read 0 while bInputsValid is FALSE, as in test_templates.py; a master that keeps
the last inputs instead records them frozen.

This is a simulated drive. The files show what the FB's text does against the profile's
state machine, not what any drive does. Keep the CSV files outside the repository.
"""
import argparse
import csv
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from st_subset import Struct  # noqa: E402
from test_templates import CYCLE, PROGRAM, Rig, SimDrive, ramp  # noqa: E402

# The channels of bench-test.md, section 4, named as Scope names them.
COLUMNS = ('Time [ms]',
           'MAIN.stAxis1.nControlword', 'MAIN.stAxis1.nStatusword',
           'MAIN.stAxis1.nModesOfOperation', 'MAIN.stAxis1.nModesDisplay',
           'MAIN.stAxis1.nPositionActual', 'MAIN.stAxis1.nTargetPosition',
           'MAIN.fbAxis1.bValid', 'MAIN.fbAxis1.bBusy', 'MAIN.fbAxis1.bError',
           'MAIN.fbAxis1.nErrorID')


class Recorder(Rig):
    """A Rig that keeps one row per scan, as Scope samples at the task cycle."""

    def __init__(self, lag):
        super().__init__(SimDrive(), lag)
        self.config = Struct(PROGRAM, 'ST_Cia402Config')  # the defaults, not the suite's
        self.rows = []

    def scan(self):
        out = super().scan()
        io = self.io
        self.rows.append((self.now - CYCLE, io['nControlword'], io['nStatusword'],
                          io['nModesOfOperation'], io['nModesDisplay'],
                          io['nPositionActual'], io['nTargetPosition'],
                          int(out['bValid']), int(out['bBusy']), int(out['bError']),
                          out['nErrorID']))
        return out

    def toggle_enable(self):
        self.enable = False
        self.scan()
        self.enable = True


def until_seconds(rig, condition, seconds, what):
    return rig.until(condition, limit=int(seconds * 1000 / CYCLE), what=what)


def quick_stop_pulse(rig):
    rig.quick_stop = True
    rig.scan()
    rig.quick_stop = False
    rig.at_rest()


def s1(rig):
    rig.run(20)


def s2(rig):
    rig.enable, rig.mode = True, 8
    rig.valid()
    rig.run(20)


def s3(rig):
    rig.enable = False
    rig.at_rest()
    rig.run(20)


def s4(rig):
    rig.enable, rig.mode = True, 8
    rig.valid()
    rig.run(10)
    rig.caller = ramp(5)                  # 300 increments in small steps
    rig.run(60)
    rig.caller = None
    rig.run(20)


def s5(rig):
    rig.run(10)
    quick_stop_pulse(rig)                 # at standstill
    rig.run(20)                           # bEnable TRUE does not restart it
    rig.toggle_enable()
    rig.valid()
    rig.caller = ramp(5)
    rig.run(20)
    quick_stop_pulse(rig)                 # moving
    rig.caller = None
    rig.run(20)
    rig.toggle_enable()
    rig.valid()


def s6(rig):
    rig.run(10)
    rig.drive.fault()
    rig.error(0x8110)
    rig.run(20)


def s7(rig):
    rig.pulse_reset()
    rig.at_rest()
    rig.run(50)                           # stays down with bEnable TRUE
    rig.toggle_enable()
    rig.valid()
    rig.run(20)


def s8(rig):
    rig.drive.fault(persists=True)
    rig.error(0x8110)
    rig.run(10)
    rig.pulse_reset()
    until_seconds(rig, lambda r: r.out['nErrorID'] == 0x8111, 30, 'three failed resets')
    rig.run(20)
    rig.drive.fault_persists = False      # the cause cleared
    rig.pulse_reset()
    rig.at_rest()
    rig.toggle_enable()
    rig.valid()
    rig.run(20)


def homing(rig):
    rig.mode = 6
    until_seconds(rig, lambda r: r.out['bValid'] and r.io['nModesDisplay'] == 6, 10,
                  'homed')
    rig.run(20)


def s9(rig):
    homing(rig)


def s10(rig):
    rig.mode = 8
    until_seconds(rig, lambda r: r.out['bValid'] and r.io['nModesDisplay'] == 8, 10,
                  'back in CSP')
    rig.run(20)


def s11(rig):
    rig.drive.homing_scans, rig.drive.home_position = 60, 400   # a run that moves
    homing(rig)


def s12(rig):
    rig.inputs_valid = False              # the cable out, longer than tInputsInvalid
    rig.drive.fault()                     # the drive's own reaction to the lost bus
    rig.run(30)
    rig.inputs_valid = True
    rig.run(10)
    rig.pulse_reset()
    rig.at_rest()
    rig.toggle_enable()
    rig.valid()
    rig.run(20)


SCENARIOS = ((1, s1), (2, s2), (3, s3), (4, s4), (5, s5), (6, s6), (7, s7), (8, s8),
             (9, s9), (10, s10), (11, s11), (12, s12))


def run(lag=1):
    """{scenario number: rows} for one run of every scenario in order; raises if the
    simulated drive saw the FB break a rule."""
    rig = Recorder(lag)
    result = {}
    for number, scenario in SCENARIOS:
        start = len(rig.rows)
        scenario(rig)
        if rig.drive.violations:
            raise AssertionError(f'scenario {number}: {rig.drive.violations}')
        result[number] = rig.rows[start:]
    return result


def write(rows, path):
    with open(path, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(COLUMNS)
        w.writerows(rows)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    p.add_argument('out_dir', help='where to write scenario_N.csv, outside the repository')
    p.add_argument('--lag', type=int, default=1, help='statusword lag in cycles (default 1)')
    a = p.parse_args(argv)
    os.makedirs(a.out_dir, exist_ok=True)
    for number, rows in run(a.lag).items():
        path = os.path.join(a.out_dir, f'scenario_{number}.csv')
        write(rows, path)
        print(f'{path}: {len(rows)} rows')
    return 0


if __name__ == '__main__':
    sys.exit(main())
