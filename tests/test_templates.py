"""Tests for templates/: FB_Cia402Axis run against a simulated drive, and its files.

    python3 -m unittest discover -s tests -v

The FB's own Structured Text runs in st_subset.py, a deliberately small interpreter, so
what is tested is the template's text and not a Python copy of it. The simulated drive
moves on test_cia402.model_drive, written from the controlword bit rules independently
of cia402.TRANSITIONS, and checks the ordering rules of references/state-machine.md on
every scan: it records a violation whenever the FB breaks one. Every scenario ends with
no violations, the transitions the drive took are compared with cia402.plan, and the
statusword can reach the FB late, as it does over a real bus.

None of this is a real drive. It shows that the template keeps the rules against the
profile's state machine; it cannot show what a particular drive does.
"""
import io
import os
import re
import sys
import unittest
import xml.etree.ElementTree as ET
from itertools import product

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
TEMPLATES = os.path.join(ROOT, 'templates')
sys.path.insert(0, os.path.join(ROOT, 'scripts'))
sys.path.insert(0, HERE)

import cia402  # noqa: E402
from st_subset import Program, StError, Struct, Time  # noqa: E402
from test_cia402 import model_drive  # noqa: E402

ST_FILE = os.path.join(TEMPLATES, 'FB_Cia402Axis.st')
with open(ST_FILE, encoding='utf-8') as f:
    ST_TEXT = f.read()
PROGRAM = Program(ST_TEXT)

CYCLE = 10  # ms per scan

# Statusword bits 0-6 the simulated drive reports per state, written out here rather than
# read from cia402.STATES. Bit 5 is set in the four states where it is a don't-care, which
# a decoder that masks every state with 0x6F misreads.
STATE_BITS = {
    'not_ready_to_switch_on': 0x20, 'switch_on_disabled': 0x60,
    'ready_to_switch_on': 0x21, 'switched_on': 0x23, 'operation_enabled': 0x27,
    'quick_stop_active': 0x07, 'fault_reaction_active': 0x2F, 'fault': 0x28,
}
VOLTAGE, REMOTE = 0x0010, 0x0200
MODE_BITS = 0x0370  # controlword bits 4-6, 8, 9

ENUM_OF = {
    'not_ready_to_switch_on': 'NotReadyToSwitchOn', 'switch_on_disabled': 'SwitchOnDisabled',
    'ready_to_switch_on': 'ReadyToSwitchOn', 'switched_on': 'SwitchedOn',
    'operation_enabled': 'OperationEnabled', 'quick_stop_active': 'QuickStopActive',
    'fault_reaction_active': 'FaultReactionActive', 'fault': 'Fault',
}

# Error codes, written out as templates/README.md lists them.
ERR = {'not_ready': 0x8101, 'shutdown': 0x8102, 'switch_on': 0x8103, 'enable': 0x8104,
       'mode': 0x8105, 'stop': 0x8106, 'homing_time': 0x8107, 'drive_fault': 0x8110,
       'reset_failed': 0x8111, 'quick_stop': 0x8112, 'left_state': 0x8113,
       'homing': 0x8114, 'statusword': 0x8115, 'no_mode': 0x8120, 'no_quick_stop': 0x8108}

# Short timeouts keep the scenarios to a few hundred scans.
FAST = {'tStateTimeout': Time(200), 'tStopTimeout': Time(500), 'tHomingTimeout': Time(1000),
        'tResetPause': Time(100), 'tStandstill': Time(50), 'nResetAttempts': 3,
        'nStandstillWindow': 0}

# Which set-point each mode follows.
POSITION, VELOCITY, TORQUE = (1, 8), (3, 9), (4, 10, 11)
FOLLOWED = {'target': (8,), 'velocity': (3, 9), 'torque': (4, 10, 11)}

SOD, OE = 'switch_on_disabled', 'operation_enabled'


class SimDrive:
    """A CiA 402 drive for the FB to talk to. step() takes the FB's outputs for one
    cycle; statusword(), display and position are what the drive reports back."""

    def __init__(self, state=SOD, position=1000, modes=(1, 3, 4, 6, 8, 9, 10),
                 quick_stop_stays=False, settle=1, mode_delay=2, qs_ramp=10,
                 homing_scans=8, home_position=0, homing_phase=0x0400, homing_fails=False,
                 boot_scans=5, fra_scans=3, jitter=0, refuse=(), ignores_bit_2=False):
        self.state, self.position, self.modes = state, position, modes
        self.quick_stop_stays, self.settle, self.mode_delay = quick_stop_stays, settle, mode_delay
        self.qs_ramp, self.homing_scans, self.home_position = qs_ramp, homing_scans, home_position
        self.homing_phase, self.homing_fails = homing_phase, homing_fails
        self.boot_scans, self.fra_scans, self.jitter = boot_scans, fra_scans, jitter
        self.refuse = refuse  # states this drive will not move to when commanded
        self.ignores_bit_2 = ignores_bit_2  # reads controlword bit 2 as 1: no quick stop
        self.display = 0
        self.fault_persists = False
        self.override_sw = None
        self.ramp_left = qs_ramp if state == 'quick_stop_active' else 0
        self.homing_left = None
        self.timer = 0              # scans spent in a state the drive leaves by itself
        self.recent = []            # the last raw controlwords, for settle
        self.accepted = self.prev_accepted = 0
        self.last = None            # the FB's outputs of the previous cycle
        self.mode_queue = []
        self.transitions = []       # (from, to, controlword or None if by itself)
        self.violations = []
        self.scan = 0
        self.jitter_sign = 1
        self.lag = 0                # cycles late the FB sees the statusword (set by Rig)
        self.states = []            # the state at the start of each cycle

    def statusword(self):
        if self.override_sw is not None:
            return self.override_sw
        sw = STATE_BITS[self.state] | VOLTAGE | REMOTE
        if self.state == OE and self.display == 6:
            sw |= self.homing_phase
        return sw

    # events from outside the FB

    def fault(self, persists=False):
        self.fault_persists = persists
        self._move('fault_reaction_active', None)
        self.timer = 0

    def external_quick_stop(self):
        assert self.state == OE
        self._move('quick_stop_active', None)

    def drop(self, state):
        self._move(state, None)

    # one cycle

    def violation(self, text):
        self.violations.append(f'scan {self.scan}: {text}')

    def _move(self, to, cw):
        if to != self.state:
            self.transitions.append((self.state, to, cw))
            self.state = to
            if to == 'quick_stop_active':
                self.ramp_left = self.qs_ramp

    def step(self, cw, mode_out, target, velocity, torque, enabled, valid):
        self.scan += 1
        before, position = self.state, self.position
        self.states.append(before)
        # The state the FB could have seen. A word that only a later statusword could
        # have changed is judged against it; what the drive does is judged against
        # `before`.
        seen = self.states[max(0, len(self.states) - 1 - self.lag)]
        self._check_words(cw, before, seen, enabled, valid)
        self._check_setpoints(cw, mode_out, target, velocity, torque, before, valid)

        self.recent = (self.recent + [cw])[-self.settle:]
        self.prev_accepted = self.accepted
        if len(self.recent) == self.settle and len(set(self.recent)) == 1:
            self.accepted = cw
        accepted = self.accepted

        # Commanded transitions, then the ones the drive takes by itself.
        word = accepted | 0x04 if self.ignores_bit_2 else accepted
        new = model_drive(self.state, word, self.prev_accepted, self.quick_stop_stays)
        if self.state == 'fault' and new != 'fault' and self.fault_persists:
            new = 'fault'
        if new in self.refuse:
            new = self.state
        if self.state == 'quick_stop_active' and new != self.state and self.ramp_left:
            self.violation(f'quick stop cut {self.ramp_left} scans before the motor stopped '
                           f'(controlword 0x{accepted:04X})')
        if new != self.state:
            self._entering(new, accepted, target, velocity, torque, enabled, seen)
            self._move(new, accepted)
        self._by_itself()

        # 0x6061 follows 0x6060 after a delay, for the modes the drive has.
        self.mode_queue.append(mode_out)
        if len(self.mode_queue) > self.mode_delay:
            wanted = self.mode_queue.pop(0)
            if wanted in self.modes and wanted != self.display:
                if self.state == OE:
                    self._setpoint_safe(wanted, target, velocity, torque,
                                        f'on the switch to {wanted}')
                self.display = wanted

        self._homing(accepted)
        self._motion(target)
        self.last = {'cw': cw, 'mode_out': mode_out, 'target': target,
                     'velocity': velocity, 'torque': torque, 'position': position}

    def _check_words(self, cw, state, seen, enabled, valid):
        if cw & 0x80 and cw & 0x0F:
            self.violation(f'0x{cw:04X}: fault reset with the enable bits')
        if cw & 0x80 and seen != 'fault':
            self.violation(f'0x{cw:04X}: bit 7 sent in {seen}')
        if state == OE and not cw & 0x02:
            self.violation(f'0x{cw:04X}: Disable voltage from Operation enabled (T9)')
        if seen == 'quick_stop_active' and cw & 0x8F == 0x0F:
            self.violation(f'0x{cw:04X}: Enable operation in Quick stop active (T16)')
        if not enabled and cw & 0x8F == 0x0F:
            self.violation(f'0x{cw:04X}: Enable operation sent with bEnable FALSE or a '
                           f'quick stop held')
        if cw & 0x10 and self.display != 6 and not valid:
            self.violation(f'0x{cw:04X}: bit 4 sent in mode {self.display} before bValid')

    def _check_setpoints(self, cw, mode_out, target, velocity, torque, state, valid):
        last = self.last
        if last is None:
            return
        if mode_out != last['mode_out'] and not self._was_safe_for(mode_out, last):
            self.violation(f'0x6060 = {mode_out} written before its set-point was safe')
        if state == OE and not valid:
            for key, value in (('target', target), ('velocity', velocity),
                               ('torque', torque)):
                if self.display in FOLLOWED[key] and value != last[key]:
                    self.violation(f'{key} stepped from {last[key]} to {value} by the FB '
                                   f'while the drive followed it')

    @staticmethod
    def _was_safe_for(mode, last):
        if last['cw'] & MODE_BITS:
            return False
        if mode in POSITION:
            return last['target'] == last['position']
        if mode in VELOCITY:
            return last['velocity'] == 0
        if mode in TORQUE:
            return last['torque'] == 0
        return True

    def _entering(self, new, cw, target, velocity, torque, enabled, seen):
        if new != OE:
            return
        if not enabled:
            self.violation('Operation enabled entered with bEnable FALSE or a quick stop held')
        # Seen in Operation enabled, the word was not T4: it was holding that state, and a
        # drive that has just dropped out, unseen, climbed back on it.
        if cw & MODE_BITS and seen != OE:
            self.violation(f'enabled with mode bits set: 0x{cw:04X}')
        self._setpoint_safe(self.display, target, velocity, torque, 'on enable')

    def _setpoint_safe(self, mode, target, velocity, torque, when):
        if mode == 8 and target != self.position:
            self.violation(f'CSP jump {when}: target {target}, actual {self.position}')
        if mode in VELOCITY and velocity:
            self.violation(f'velocity {velocity} {when}')
        if mode in TORQUE and torque:
            self.violation(f'torque {torque} {when}')

    def _by_itself(self):
        self.timer += 1
        if self.state == 'not_ready_to_switch_on' and self.timer > self.boot_scans:
            self._move(SOD, None)
        elif self.state == 'fault_reaction_active' and self.timer > self.fra_scans:
            self._move('fault', None)
        elif self.state == 'quick_stop_active' and self.ramp_left:
            self.position += self.ramp_left  # decelerating
            self.ramp_left -= 1
            if not self.ramp_left and not self.quick_stop_stays:
                self._move(SOD, None)
        if self.state not in ('not_ready_to_switch_on', 'fault_reaction_active'):
            self.timer = 0

    def _homing(self, cw):
        if self.state != OE or self.display != 6:
            self.homing_left = None
            return
        if cw & 0x10 and not self.prev_accepted & 0x10:
            self.homing_phase, self.homing_left = 0x0000, self.homing_scans
        if self.homing_left is None:
            return
        if not cw & 0x10:
            self.homing_phase, self.homing_left = 0x0400, None  # interrupted
        elif self.homing_left == 0:
            if self.homing_fails:
                self.homing_phase = 0x2400
            else:
                self.homing_phase, self.position = 0x1400, self.home_position
            self.homing_left = None
        else:
            self.position += 5
            self.homing_left -= 1

    def _motion(self, target):
        if self.state == OE and self.display == 8:
            # CSP with a following error: halfway to the target each cycle.
            diff = target - self.position
            self.position += diff if abs(diff) <= 2 else diff // 2
        elif self.jitter and not self.ramp_left and self.homing_left is None:
            self.position += self.jitter * self.jitter_sign
            self.jitter_sign = -self.jitter_sign


class Rig:
    """The FB, its drive and the inputs the test sets; scan() runs one cycle. The FB
    reads what the drive reported `lag` cycles earlier."""

    def __init__(self, drive, lag=0, copy_position=True, **config):
        self.drive, self.lag, self.copy_position = drive, lag, copy_position
        drive.lag = lag
        self.fb = PROGRAM.instance('FB_Cia402Axis')
        self.io = Struct(PROGRAM, 'ST_Cia402Drive')
        self.config = Struct(PROGRAM, 'ST_Cia402Config')
        for name, value in dict(FAST, **config).items():
            self.config[name] = value
        self.enable, self.mode, self.reset, self.quick_stop = False, 0, False, False
        self.stop_held = False  # a quick stop was asked for and has not been released
        self.caller = None  # writes set-points after the call while bValid
        self.always = None  # writes before the call, valid or not
        self.history = []
        self.now = 0
        self.words = []     # every controlword the FB wrote
        self.out = None

    def scan(self):
        d = self.drive
        self.history.append((d.statusword(), d.display, d.position))
        if self.quick_stop:
            self.stop_held = True
        elif not self.enable and d.state in (SOD, 'not_ready_to_switch_on'):
            self.stop_held = False
        sw, display, position = self.history[max(0, len(self.history) - 1 - self.lag)]
        self.io['nStatusword'] = sw
        self.io['nModesDisplay'] = display
        if self.copy_position:
            self.io['nPositionActual'] = position
        if self.always:
            self.always(self)
        self.out = self.fb.scan(self.now, bEnable=self.enable, nMode=self.mode,
                                bReset=self.reset, bQuickStop=self.quick_stop,
                                stConfig=self.config, stDrive=self.io)
        if self.out['bValid'] and self.caller:
            self.caller(self)
        cw = self.io['nControlword']
        self.words.append(cw)
        d.step(cw, self.io['nModesOfOperation'], self.io['nTargetPosition'],
               self.io['nTargetVelocity'], self.io['nTargetTorque'],
               self.enable and not self.stop_held, self.out['bValid'])
        self.now += CYCLE
        return self.out

    def run(self, scans):
        for _ in range(scans):
            self.scan()
        return self.out

    def until(self, condition, limit=400, what='the condition'):
        for n in range(limit):
            self.scan()
            if condition(self):
                return n + 1
        raise AssertionError(f'{what} not reached in {limit} scans: drive in '
                             f'{self.drive.state}, FB step {self.fb["eStep"]}, '
                             f'outputs {self.out}, violations {self.drive.violations}')

    def pulse_reset(self):
        self.reset = True
        self.scan()
        self.reset = False

    def valid(self, limit=400):
        return self.until(lambda r: r.out['bValid'], limit, 'bValid')

    def at_rest(self):
        return self.until(lambda r: r.drive.state == SOD and not r.out['bBusy'],
                          what='rest in Switch on disabled')

    def error(self, code):
        n = self.until(lambda r: r.out['bError'], what=f'error 0x{code:04X}')
        if self.out['nErrorID'] != code:
            raise AssertionError(f'error 0x{self.out["nErrorID"]:04X}, expected '
                                 f'0x{code:04X}')
        return n

    def distinct_words(self, start=0):
        """The controlwords written from scan `start` on, repeats collapsed."""
        seq = []
        for w in self.words[start:]:
            if not seq or seq[-1] != w:
                seq.append(w)
        return seq

    def edges_of_bit_7(self, start=0):
        w = self.words[start:]
        return [i for i in range(1, len(w)) if w[i] & 0x80 and not w[i - 1] & 0x80]


def ramp(step):
    """A caller that moves the CSP target by `step` each cycle."""
    return lambda r: r.io.__setitem__('nTargetPosition', r.io['nTargetPosition'] + step)


def plan_transitions(start, target, mode=None, quick_stop_stays=False):
    """(from, to, controlword or None) for each state change in cia402.plan."""
    result = cia402.plan(start, target, cia402.resolve_mode(mode) if mode else None,
                         quick_stop_stays)
    out, state = [], start
    for step in result['steps']:
        if step['transition'] is None:
            continue
        out.append((state, step['expect'], step['controlword']))
        state = step['expect']
    return out


def way_down_transitions(start):
    """plan_transitions to Switch on disabled, with the word the FB sends for T7 and T10 while
    0x000F may still be on its way: 0x0002, which is T11 and not T9 if the drive has climbed
    back unseen. The plan's 0x0000 is right for a caller with no bit 3 left to land."""
    return [(a, b, 0x0002 if a in ('ready_to_switch_on', 'switched_on') else cw)
            for a, b, cw in plan_transitions(start, SOD)]


class TemplateCase(unittest.TestCase):
    """Every rig a test makes must end without a violation."""

    def setUp(self):
        self.rigs = []

    def tearDown(self):
        for rig in self.rigs:
            self.assertEqual(rig.drive.violations, [])

    def make(self, lag=0, copy_position=True, config=None, **drive):
        rig = Rig(SimDrive(**drive), lag, copy_position, **(config or {}))
        self.rigs.append(rig)
        return rig

    def running(self, mode=8, lag=0, config=None, **drive):
        rig = self.make(lag, config=config, **drive)
        rig.enable, rig.mode = True, mode
        rig.valid()
        return rig

    def persistent_fault(self, lag=0, config=None):
        rig = self.running(lag=lag, config=config)
        rig.drive.fault(persists=True)
        rig.error(ERR['drive_fault'])
        rig.run(10)
        return rig

    def in_step(self, rig, step):
        """bReset, then on to `step`: the drive stays in Fault that long."""
        rig.pulse_reset()
        rig.until(lambda r: r.fb['eStep'].name == step, what=step)


class Decode(TemplateCase):

    def test_every_statusword_pattern_against_the_decoder(self):
        # The states depend on bits 0-6 only; three settings of the high bits on top.
        # A fresh FB for each word: after another state, Not ready counts as Unknown.
        config = Struct(PROGRAM, 'ST_Cia402Config')
        for high in (0x0000, 0x0200, 0xFF80):
            for low in range(0x80):
                sw = high | low
                io = Struct(PROGRAM, 'ST_Cia402Drive')
                io['nStatusword'] = sw
                out = PROGRAM.instance('FB_Cia402Axis').scan(
                    0, bEnable=False, nMode=0, bReset=False, stConfig=config, stDrive=io)
                r = cia402.decode_statusword(sw)
                key = r['state'] or (r['treat_as'] if r['treat_as'] in
                                     ('fault', 'fault_reaction_active') else None)
                with self.subTest(sw=f'0x{sw:04X}'):
                    self.assertEqual(out['eDriveState'].name, ENUM_OF.get(key, 'Unknown'))


class Enabling(TemplateCase):

    def test_from_each_state_as_the_planner_says(self):
        # Enabling starts from Switch on disabled: from above it, the way down first.
        for start in (SOD, 'not_ready_to_switch_on', 'quick_stop_active',
                      'ready_to_switch_on', 'switched_on', OE):
            with self.subTest(start=start):
                rig = self.make(state=start, modes=(8,))
                if start == OE:
                    rig.drive.display = 8
                rig.enable, rig.mode = True, 8
                rig.valid()
                expected = plan_transitions(start, OE, 'csp')
                if start in ('ready_to_switch_on', 'switched_on', OE):
                    expected = way_down_transitions(start) + plan_transitions(SOD, OE, 'csp')
                self.assertEqual(rig.drive.transitions, expected)

    def test_from_fault_after_a_reset(self):
        rig = self.make(state='fault')
        rig.enable, rig.mode = True, 8
        rig.error(ERR['drive_fault'])
        self.assertEqual(rig.words[-1], 0x0000)
        mark = len(rig.words)
        rig.pulse_reset()
        rig.valid()
        self.assertEqual(rig.drive.transitions, plan_transitions('fault', OE, 'csp'))
        # Bit 7 low before the edge, released after it, then the way up.
        self.assertEqual(rig.distinct_words(mark), [0x0000, 0x0080, 0x0000, 0x0006,
                                                    0x0007, 0x000F])

    def test_csp_target_follows_actual_until_valid(self):
        rig = self.make(position=-123456)
        rig.enable, rig.mode = True, 8
        rig.valid()
        self.assertEqual(rig.io['nTargetPosition'], -123456)
        self.assertEqual(rig.io['nModesOfOperation'], 8)

    def test_csv_and_cst_enable_with_zero_set_points(self):
        for mode, member in ((9, 'nTargetVelocity'), (10, 'nTargetTorque')):
            with self.subTest(mode=mode):
                rig = self.make()
                rig.io[member] = 500  # left over from before
                rig.enable, rig.mode = True, mode
                rig.valid()
                self.assertEqual(rig.io[member], 0)

    def test_set_points_are_the_callers_once_valid(self):
        rig = self.running(position=500)
        rig.caller = ramp(7)
        rig.run(10)
        self.assertEqual(rig.io['nTargetPosition'], 570)
        self.assertTrue(rig.out['bValid'])

    def test_mode_bits_pass_only_while_valid(self):
        rig = self.make()
        rig.always = lambda r: r.io.__setitem__('nModeBits', MODE_BITS)
        rig.enable, rig.mode = True, 1
        rig.valid()
        self.assertTrue(all(w & MODE_BITS == 0 for w in rig.words))
        rig.scan()
        self.assertEqual(rig.words[-1], 0x000F | MODE_BITS)

    def test_stale_mode_bits_are_cleared_before_valid(self):
        # A PP handshake cut short by a fault leaves bits 4 and 6 behind.
        rig = self.running(mode=1)
        rig.io['nModeBits'] = 0x0050
        rig.drive.fault()
        rig.error(ERR['drive_fault'])
        rig.run(10)
        rig.pulse_reset()
        rig.valid()
        rig.run(3)
        self.assertEqual(rig.io['nModeBits'], 0)
        self.assertEqual(rig.words[-1], 0x000F)

    def test_mode_zero_is_an_error(self):
        rig = self.make()
        rig.enable = True
        rig.error(ERR['no_mode'])


class Disabling(TemplateCase):

    def test_way_down_from_operation_enabled_as_the_planner_says(self):
        rig = self.running()
        mark = len(rig.drive.transitions)
        rig.enable = False
        rig.at_rest()
        self.assertEqual(rig.drive.transitions[mark:], way_down_transitions(OE))

    def test_way_down_from_each_other_state(self):
        for start in ('ready_to_switch_on', 'switched_on'):
            with self.subTest(start=start):
                rig = self.make(state=start)
                rig.at_rest()
                self.assertEqual(rig.drive.transitions, way_down_transitions(start))

    def test_way_down_takes_one_word_per_state_and_no_timer(self):
        # T5 on the first scan, T10 as soon as the statusword shows Switched on.
        for lag in (0, 1, 2, 3):
            with self.subTest(lag=lag):
                rig = self.running(lag=lag)
                rig.enable = False
                n = rig.until(lambda r: r.drive.state == SOD, what='way down')
                self.assertEqual(n, 2 + lag)

    def test_set_points_are_held_on_the_way_down(self):
        # Moving in CSP with a following error: the FB must not pull the target back.
        rig = self.running(position=0)
        rig.caller = ramp(40)
        rig.run(10)
        rig.enable = False
        rig.at_rest()

    def test_disabled_at_rest_is_neither_busy_nor_valid(self):
        rig = self.make()
        rig.run(20)
        self.assertFalse(rig.out['bBusy'])
        self.assertFalse(rig.out['bValid'])
        self.assertEqual(set(rig.words), {0x0000})

    def test_stop_that_does_not_end_is_an_error(self):
        rig = self.running()
        rig.drive.refuse = ('switched_on',)
        rig.enable = False
        rig.error(ERR['stop'])
        self.assertEqual(rig.words[-1], 0x0007)  # still asking for the stop


class QuickStop(TemplateCase):

    STAYS = {'bQuickStopStays': True}

    def test_external_quick_stop_is_left_to_finish(self):
        rig = self.running()
        rig.drive.external_quick_stop()
        mark = len(rig.words)
        rig.error(ERR['quick_stop'])
        rig.until(lambda r: r.drive.state == SOD, what='end of the stop')
        self.assertEqual(set(rig.words[mark:mark + rig.drive.qs_ramp]), {0x0002})
        rig.run(3)
        self.assertEqual(rig.words[-1], 0x0000)
        rig.pulse_reset()
        rig.valid()

    def test_quick_stop_that_stays_is_left_at_standstill(self):
        rig = self.running(quick_stop_stays=True, config=self.STAYS)
        rig.drive.external_quick_stop()
        mark = len(rig.words)
        rig.until(lambda r: r.drive.state == SOD, what='T12')
        cut = rig.words.index(0x0000, mark) - mark
        # The ramp, then tStandstill without motion: standstill, not a fixed delay.
        self.assertGreaterEqual(cut, rig.drive.qs_ramp + 50 // CYCLE)
        self.assertEqual(rig.drive.transitions[-1], ('quick_stop_active', SOD, 0x0000))

    def test_quick_stop_that_stays_without_the_flag_is_held(self):
        rig = self.running(quick_stop_stays=True)
        rig.drive.external_quick_stop()
        rig.run(200)
        self.assertEqual(rig.drive.state, 'quick_stop_active')
        self.assertEqual(rig.words[-1], 0x0002)

    def test_jitter_without_a_band_holds_the_quick_stop(self):
        rig = self.running(quick_stop_stays=True, jitter=1, config=self.STAYS)
        rig.drive.external_quick_stop()
        rig.run(200)
        self.assertEqual(rig.drive.state, 'quick_stop_active')
        self.assertEqual(rig.words[-1], 0x0002)

    def test_a_band_over_the_jitter_finds_standstill(self):
        rig = self.running(quick_stop_stays=True, jitter=1,
                           config=dict(self.STAYS, nStandstillWindow=2))
        rig.drive.external_quick_stop()
        rig.until(lambda r: r.drive.state == SOD, what='T12')

    def test_quick_stop_is_not_cut_when_0x6064_is_not_copied(self):
        # The position the FB reads never moves; the drive must still end the stop.
        rig = self.make(copy_position=False, qs_ramp=40)
        rig.enable, rig.mode = True, 9
        rig.valid()
        rig.drive.external_quick_stop()
        rig.until(lambda r: r.drive.state == SOD, what='end of the stop')

    def test_starting_in_a_quick_stop_that_stays(self):
        rig = self.make(state='quick_stop_active', quick_stop_stays=True, config=self.STAYS)
        rig.enable, rig.mode = True, 8
        rig.valid()
        self.assertEqual(rig.drive.transitions[0], ('quick_stop_active', SOD, 0x0000))


class CommandedQuickStop(TemplateCase):
    """bQuickStop, wired as a line stop: bEnable := bRun, bQuickStop := NOT bLineOk."""

    STAYS = {'bQuickStopStays': True}

    def held_down(self, rig):
        """The drive stays in Switch on disabled and the FB neither enables nor waits.
        The first scans are left out: a late statusword can still show the state above."""
        rig.run(30)
        self.assertEqual(rig.drive.state, SOD)
        self.assertFalse(rig.out['bBusy'])
        self.assertFalse(rig.out['bValid'])
        self.assertEqual(rig.words[-20:], [0x0000] * 20)

    def ask(self, rig, pulse):
        """bQuickStop left TRUE, or a pulse of one scan."""
        rig.quick_stop = True
        if pulse:
            rig.scan()
            rig.quick_stop = False

    def test_t11_goes_out_at_once_and_is_held(self):
        rig = self.running()
        mark, start = len(rig.drive.transitions), len(rig.words)
        rig.quick_stop = True
        rig.scan()
        self.assertFalse(rig.out['bValid'])
        self.assertTrue(rig.out['bBusy'])
        rig.at_rest()
        self.assertEqual(set(rig.words[start:start + rig.drive.qs_ramp]), {0x0002})
        self.assertEqual(rig.drive.transitions[mark:],
                         plan_transitions(OE, 'quick_stop_active')
                         + plan_transitions('quick_stop_active', SOD))
        self.assertFalse(rig.out['bError'])
        self.assertEqual(rig.out['nErrorID'], 0)

    def test_line_stop_restarts_only_once_the_line_is_ok_and_run_is_set_again(self):
        rig = self.running(mode=3)
        rig.quick_stop = True   # bLineOk falls
        rig.at_rest()
        self.held_down(rig)
        rig.quick_stop = False  # bLineOk back, bRun still TRUE
        self.held_down(rig)
        rig.enable = False      # bRun dropped...
        rig.scan()
        rig.enable = True       # ...and set again
        rig.valid()

    def test_enable_does_not_restart_while_the_stop_is_asked(self):
        rig = self.running()
        rig.quick_stop = True
        rig.at_rest()
        rig.enable = False
        rig.run(3)
        rig.enable = True
        self.held_down(rig)

    def test_a_pulse_runs_to_the_end(self):
        rig = self.running()
        rig.quick_stop = True
        rig.scan()
        rig.quick_stop = False
        rig.at_rest()
        self.held_down(rig)

    def test_asked_at_rest_it_blocks_enabling(self):
        rig = self.make()
        rig.quick_stop = True
        rig.run(3)
        rig.enable, rig.mode = True, 8
        self.held_down(rig)
        rig.enable, rig.quick_stop = False, False
        rig.scan()
        rig.enable = True
        rig.valid()

    def test_a_ramp_longer_than_the_stop_timeout_is_no_error(self):
        rig = self.running(qs_ramp=80)  # tStopTimeout is 50 scans here
        rig.quick_stop = True
        rig.at_rest()
        self.assertFalse(rig.out['bError'])

    def test_a_long_run_before_it_is_no_timeout(self):
        # Running never re-arms the step timer, so it has long expired by the entry scan.
        rig = self.running()
        rig.run(100)
        rig.quick_stop = True
        rig.at_rest()
        self.assertFalse(rig.out['bError'])

    def test_on_a_drive_that_stays_it_leaves_at_standstill(self):
        rig = self.running(quick_stop_stays=True, config=self.STAYS)
        mark = len(rig.words)
        rig.quick_stop = True
        rig.at_rest()
        self.assertGreaterEqual(rig.words.index(0x0000, mark) - mark,
                                rig.drive.qs_ramp + 50 // CYCLE)
        self.assertEqual(rig.drive.transitions[-1],
                         plan_transitions('quick_stop_active', SOD, quick_stop_stays=True)[0])
        self.held_down(rig)

    def test_on_a_drive_that_stays_without_the_flag_it_is_held(self):
        rig = self.running(quick_stop_stays=True)
        rig.quick_stop = True
        rig.run(100)
        rig.quick_stop = False
        rig.run(100)
        self.assertEqual(rig.drive.state, 'quick_stop_active')
        self.assertEqual(rig.words[-1], 0x0002)
        self.assertFalse(rig.out['bError'])

    def test_a_drive_that_refuses_t11_is_taken_down_with_t5(self):
        # The stop input must never leave an axis harder to stop than bEnable FALSE does.
        for enable in (True, False):
            with self.subTest(enable=enable):
                rig = self.running(refuse=('quick_stop_active',))
                mark = len(rig.drive.transitions)
                rig.quick_stop, rig.enable = True, enable
                n = rig.error(ERR['no_quick_stop'])
                self.assertGreaterEqual(n * CYCLE, 200)  # tStateTimeout
                rig.at_rest()
                self.assertEqual(rig.drive.transitions[mark:], plan_transitions(OE, SOD))

    def test_in_an_error_an_enabled_drive_still_gets_t11(self):
        for pulse in (False, True):
            with self.subTest(pulse=pulse):
                rig = self.running()
                rig.drive.refuse = ('switched_on',)
                rig.enable = False
                rig.error(ERR['stop'])
                self.ask(rig, pulse)
                rig.at_rest()
                self.assertEqual(rig.drive.transitions[-2:],
                                 plan_transitions(OE, 'quick_stop_active')
                                 + plan_transitions('quick_stop_active', SOD))
                self.assertEqual(rig.out['nErrorID'], ERR['stop'])

    def test_in_an_error_a_refused_t11_falls_back_to_t5(self):
        rig = self.running()
        rig.drive.refuse = ('switched_on', 'quick_stop_active')
        rig.enable = False
        rig.error(ERR['stop'])
        self.ask(rig, pulse=True)
        rig.run(5)
        self.assertEqual(rig.words[-1], 0x0002)
        rig.run(20)  # tStateTimeout
        self.assertEqual(rig.words[-1], 0x0007)

    def test_an_undecodable_statusword_gets_0x0002_as_well(self):
        rig = self.running()
        rig.drive.override_sw = 0x0005
        rig.quick_stop = True
        rig.scan()
        self.assertEqual(rig.words[-1], 0x0002)
        self.assertEqual(rig.drive.state, 'quick_stop_active')
        rig.drive.override_sw = None
        rig.at_rest()

    def test_fault_during_the_stop(self):
        for pulse in (False, True):
            with self.subTest(pulse=pulse):
                rig = self.running()
                self.ask(rig, pulse)
                rig.run(3)
                rig.drive.fault()
                rig.error(ERR['drive_fault'])
                rig.run(10)
                rig.pulse_reset()
                rig.at_rest()
                self.assertFalse(rig.out['bError'])
                self.held_down(rig)

    def test_a_fault_while_held_down_does_not_release_it(self):
        rig = self.running()
        rig.quick_stop = True
        rig.at_rest()
        rig.quick_stop = False
        rig.run(3)
        rig.drive.fault()
        rig.error(ERR['drive_fault'])
        rig.run(10)
        rig.pulse_reset()
        rig.at_rest()
        self.held_down(rig)
        rig.enable = False
        rig.scan()
        rig.enable = True
        rig.valid()

    def test_a_bad_statusword_while_held_down_does_not_release_it(self):
        rig = self.running()
        rig.quick_stop = True
        rig.at_rest()
        rig.quick_stop = False
        rig.run(3)
        rig.drive.override_sw = 0x0005
        rig.error(ERR['statusword'])
        rig.drive.override_sw = None
        rig.pulse_reset()
        rig.at_rest()
        self.held_down(rig)

    def test_asked_in_an_error_it_holds_after_the_reset(self):
        rig = self.running()
        rig.drive.drop(SOD)
        rig.error(ERR['left_state'])
        self.ask(rig, pulse=True)
        rig.pulse_reset()
        rig.at_rest()
        self.held_down(rig)

    def test_asked_while_the_drive_boots(self):
        rig = self.make(state='not_ready_to_switch_on')
        rig.enable, rig.mode = True, 8
        rig.quick_stop = True
        rig.at_rest()
        self.held_down(rig)

    def test_bit_4_drops_in_the_middle_of_homing(self):
        rig = self.make(homing_scans=10000)
        rig.enable, rig.mode = True, 6
        rig.until(lambda r: r.words[-1] == 0x001F, what='bit 4')
        rig.quick_stop = True
        rig.scan()
        self.assertEqual(rig.words[-1], 0x0002)
        rig.at_rest()

    def test_in_the_middle_of_a_mode_switch(self):
        rig = self.running(mode_delay=20)
        rig.mode = 9
        rig.run(3)
        rig.quick_stop = True
        rig.at_rest()
        self.held_down(rig)

    def test_restart_in_csp_does_not_jump(self):
        # Moving with a following error; the ramp then moves the motor on by itself.
        rig = self.running(position=0)
        rig.caller = ramp(40)
        rig.run(10)
        rig.quick_stop = True
        rig.at_rest()
        rig.enable, rig.quick_stop, rig.caller = False, False, None
        rig.scan()
        rig.enable = True
        rig.valid()
        self.assertEqual(rig.io['nTargetPosition'], rig.drive.position)

    def test_raised_at_every_scan_of_the_way_up(self):
        # In Switched on with a T4 still on its way, 0x0000 would be T9.
        for lag, pulse in product((0, 1, 2, 3), (False, True)):
            for at in range(len(self.running(lag=lag).words) + 2):
                with self.subTest(lag=lag, pulse=pulse, at=at):
                    rig = self.make(lag=lag)
                    rig.enable, rig.mode = True, 8
                    rig.run(at)
                    self.ask(rig, pulse)
                    rig.at_rest()
                    self.held_down(rig)

    def test_raised_at_every_scan_of_the_way_down(self):
        for lag, pulse in product((0, 1, 2, 3), (False, True)):
            for at in range(6):
                with self.subTest(lag=lag, pulse=pulse, at=at):
                    rig = self.running(lag=lag)
                    rig.enable = False
                    rig.run(at)
                    self.ask(rig, pulse)
                    rig.at_rest()
                    rig.enable = True
                    if pulse:
                        rig.valid()  # down with both FALSE: this was the new bEnable
                    else:
                        self.held_down(rig)

    def test_raised_as_the_drive_leaves_fault_by_itself_in_a_reset(self):
        for lag, pulse, step in product((0, 1, 2, 3), (False, True), ('ResetLow', 'ResetPause')):
            with self.subTest(lag=lag, pulse=pulse, step=step):
                rig = self.persistent_fault(lag)
                self.in_step(rig, step)
                self.ask(rig, pulse)
                rig.drive.drop(SOD)
                rig.at_rest()
                self.assertFalse(rig.out['bError'])
                self.held_down(rig)

    def test_raised_at_every_scan_of_a_fault_reset(self):
        # The reset runs to its end: bit 7 is never left high, and the stop then holds.
        for lag, pulse in product((0, 1, 2, 3), (False, True)):
            for at in range(10):
                with self.subTest(lag=lag, pulse=pulse, at=at):
                    rig = self.running(lag=lag)
                    rig.drive.fault()
                    rig.error(ERR['drive_fault'])
                    rig.run(10)
                    rig.pulse_reset()
                    rig.run(at)
                    self.ask(rig, pulse)
                    rig.at_rest()
                    self.held_down(rig)


class FaultReset(TemplateCase):

    # (step, scans into it): ResetLow lasts cResetSettle, ResetPause tResetPause.
    OUT_OF_FAULT = [('ResetLow', 0), ('ResetLow', 1), ('ResetLow', 2), ('ResetPause', 0),
                    ('ResetPause', 1), ('ResetPause', 4), ('ResetPause', 8)]

    def test_fault_while_running_then_reset(self):
        rig = self.running()
        rig.drive.fault()
        rig.error(ERR['drive_fault'])
        rig.run(10)
        self.assertEqual(rig.words[-1], 0x0007)  # a drive in Fault ignores it: no bits 3, 7
        mark = len(rig.words)
        rig.pulse_reset()
        rig.valid()
        self.assertEqual(rig.distinct_words(mark), [0x0000, 0x0080, 0x0000, 0x0006,
                                                    0x0007, 0x000F])

    def test_failed_resets_release_bit_7_every_time(self):
        rig = self.persistent_fault()
        mark = len(rig.words)
        rig.pulse_reset()
        rig.error(ERR['reset_failed'])
        words = rig.words[mark:]
        edges = rig.edges_of_bit_7(mark)
        self.assertEqual(len(edges), 3)  # nResetAttempts
        for i in edges:
            high = 0
            while words[i + high] & 0x80:
                high += 1
            # tStateTimeout, then released. A step's word goes out on the scan it is
            # entered and its timer re-arms on the next, so allow two cycles over.
            self.assertLessEqual(high * CYCLE, 200 + 2 * CYCLE)
            self.assertEqual(words[i + high], 0x0000)
        rig.run(50)
        self.assertEqual(rig.words[-1], 0x0000)

    def test_a_drive_that_leaves_fault_by_itself_in_the_reset(self):
        # A reset the drive took late, or one from its own input: 0x0000 held, no bit 7.
        for lag, (step, at), enable in product((0, 1, 2, 3), self.OUT_OF_FAULT, (True, False)):
            with self.subTest(lag=lag, step=step, at=at, enable=enable):
                rig = self.persistent_fault(lag)
                self.in_step(rig, step)
                rig.run(at)
                self.assertEqual(rig.fb['eStep'].name, step)
                rig.enable = enable
                rig.drive.drop(SOD)
                mark = len(rig.words)
                if not enable:
                    rig.at_rest()
                    rig.enable = True
                rig.valid()
                self.assertEqual(rig.out['nErrorID'], 0)
                self.assertFalse(any(w & 0x80 for w in rig.words[mark + lag:]))

    def test_a_drive_that_leaves_fault_for_another_state_in_the_reset(self):
        for lag, (step, at) in product((0, 1, 2, 3), self.OUT_OF_FAULT):
            with self.subTest(lag=lag, step=step, at=at):
                rig = self.persistent_fault(lag)
                self.in_step(rig, step)
                rig.run(at)
                rig.drive.refuse = (SOD,)
                rig.drive.drop('ready_to_switch_on')
                mark = len(rig.words)
                rig.error(ERR['left_state'])
                self.assertFalse(any(w & 0x80 for w in rig.words[mark + lag:]))

    def test_fault_reaction_active_in_the_reset_waits_for_fault(self):
        # Still the fault: no attempt spent on it, and bit 7 only once the drive is in Fault.
        for lag, step in product((0, 1, 2, 3), ('ResetLow', 'ResetPause')):
            with self.subTest(lag=lag, step=step):
                rig = self.persistent_fault(lag)
                mark = len(rig.words)
                self.in_step(rig, step)
                rig.drive.fra_scans = 30
                rig.drive.fault(persists=True)
                rig.error(ERR['reset_failed'])
                self.assertEqual(len(rig.edges_of_bit_7(mark)), 3)

    def test_attempts_are_paused(self):
        rig = self.persistent_fault()
        mark = len(rig.words)
        rig.pulse_reset()
        rig.error(ERR['reset_failed'])
        words, edges = rig.words[mark:], rig.edges_of_bit_7(mark)
        for a, b in zip(edges, edges[1:]):
            low = b - a - sum(1 for w in words[a:b] if w & 0x80)
            self.assertGreaterEqual(low * CYCLE, 100)  # tResetPause

    def test_reset_attempts_restart_on_each_reset(self):
        rig = self.persistent_fault()
        mark = len(rig.words)
        rig.pulse_reset()
        rig.error(ERR['reset_failed'])
        rig.pulse_reset()
        rig.error(ERR['reset_failed'])
        self.assertEqual(len(rig.edges_of_bit_7(mark)), 6)

    def test_level_reset_resets_once(self):
        rig = self.persistent_fault()
        mark = len(rig.words)
        rig.reset = True
        rig.run(300)
        self.assertEqual(len(rig.edges_of_bit_7(mark)), 3)
        self.assertEqual(rig.out['nErrorID'], ERR['reset_failed'])

    def test_reset_asked_in_fault_reaction_active_is_kept(self):
        # An application that acknowledges every error at once: bReset := bError.
        rig = self.make(state='fault_reaction_active', fra_scans=10)
        rig.enable, rig.mode = True, 8
        for _ in range(300):
            rig.reset = bool(rig.out and rig.out['bError'])
            rig.scan()
            if rig.out['bValid']:
                break
        self.assertTrue(rig.out['bValid'])

    def test_reset_works_on_a_drive_that_needs_a_steady_word(self):
        rig = self.running(settle=3)
        rig.drive.fault()
        rig.error(ERR['drive_fault'])
        rig.run(10)
        rig.pulse_reset()
        rig.valid()

    def test_reset_is_never_sent_to_a_drive_not_in_fault(self):
        rig = self.running()
        rig.pulse_reset()
        rig.run(5)
        rig.enable = False
        rig.at_rest()
        rig.pulse_reset()
        rig2 = self.make(refuse=('switched_on',))
        rig2.enable, rig2.mode = True, 8
        rig2.error(ERR['switch_on'])
        rig2.pulse_reset()
        rig2.run(20)
        # In an error while the drive is still in Operation enabled: the reset
        # sequence's 0x0000 would be T9 there.
        rig3 = self.running()
        rig3.drive.refuse = ('switched_on',)
        rig3.enable = False
        rig3.error(ERR['stop'])
        rig3.pulse_reset()
        rig3.run(20)
        self.assertEqual(rig3.drive.state, OE)
        self.assertFalse(any(w & 0x80 for w in rig.words + rig2.words + rig3.words))


class ModeSwitch(TemplateCase):

    def test_switch_while_enabled_is_confirmed_on_6061(self):
        rig = self.running(position=40)
        rig.caller = ramp(3)
        rig.run(5)
        rig.caller = None
        rig.run(10)  # come to a standstill before the switch
        rig.mode = 9
        rig.scan()
        self.assertFalse(rig.out['bValid'])
        rig.valid()
        self.assertEqual(rig.drive.display, 9)
        self.assertEqual(rig.io['nModesOfOperation'], 9)
        self.assertEqual(rig.drive.state, OE)

    def test_new_modes_set_point_is_made_safe_first(self):
        # The caller leaves a velocity in 0x60FF while in CSP, where nothing reads it.
        rig = self.running()
        rig.caller = lambda r: r.io.__setitem__('nTargetVelocity', 250)
        rig.run(5)
        rig.mode = 9
        rig.valid()
        self.assertEqual(rig.io['nTargetVelocity'], 250)  # the caller's again

    def test_torque_is_held_through_a_switch_out_of_cst(self):
        # A hanging axis in CST: zero torque during the switch would let it fall.
        rig = self.running(mode=10)
        rig.caller = lambda r: r.io.__setitem__('nTargetTorque', 300)
        rig.run(5)
        rig.caller = None
        rig.mode = 8
        rig.valid()

    def test_mode_change_during_t4_goes_back_to_set_mode(self):
        for offset in range(3):
            with self.subTest(offset=offset):
                rig = self.make(lag=1)
                rig.enable, rig.mode = True, 8
                rig.until(lambda r: r.words[-1] == 0x000F, what='T4')
                rig.run(offset)
                rig.mode = 6
                rig.valid()
                self.assertEqual(rig.drive.display, 6)

    def test_change_on_the_scan_operation_enabled_shows_is_still_made_safe_first(self):
        for at in range(6):
            with self.subTest(at=at):
                rig = self.make(jitter=1)
                rig.enable, rig.mode = True, 3
                rig.until(lambda r: r.words[-1] == 0x000F, what='T4')
                rig.run(at)
                rig.mode = 8
                rig.valid()

    def test_drop_to_switched_on_during_a_switch_is_an_error(self):
        rig = self.running(mode_delay=20)
        rig.mode = 9
        rig.run(3)
        rig.drive.drop('switched_on')
        rig.error(ERR['left_state'])
        rig.run(50)
        self.assertNotEqual(rig.drive.state, OE)

    def test_unsupported_mode_times_out_and_goes_down(self):
        rig = self.running()
        mark = len(rig.drive.transitions)
        rig.mode = 7
        rig.error(ERR['mode'])
        rig.until(lambda r: r.drive.state == SOD, what='way down')
        self.assertEqual(rig.drive.transitions[mark:], way_down_transitions(OE))


class Homing(TemplateCase):

    def test_home_then_csp_from_the_new_reference(self):
        rig = self.make(position=777, home_position=-50)
        rig.enable, rig.mode = True, 6
        rig.valid()
        self.assertEqual(rig.drive.homing_phase, 0x1400)
        self.assertEqual(rig.drive.position, -50)
        self.assertIn(0x001F, rig.words)
        rig.scan()
        self.assertEqual(rig.words[-1], 0x000F)  # bit 4 low once homed
        rig.mode = 8
        rig.valid()
        self.assertEqual(rig.io['nTargetPosition'], -50)

    def test_result_of_an_earlier_run_is_not_taken_for_this_one(self):
        # A late statusword still shows the old 'completed' after bit 4 rises.
        rig = self.make(homing_phase=0x1400, homing_scans=8, lag=2)
        rig.enable, rig.mode = True, 6
        rig.until(lambda r: r.words[-1] == 0x001F, what='bit 4')
        started = len(rig.words)
        rig.valid()
        self.assertGreater(len(rig.words) - started, 8)

    def test_retry_after_a_homing_error(self):
        # The error of the failed run is still showing when bit 4 rises again.
        rig = self.make(homing_fails=True, lag=2)
        rig.enable, rig.mode = True, 6
        rig.error(ERR['homing'])
        rig.drive.homing_fails = False
        rig.at_rest()
        rig.pulse_reset()
        rig.valid()
        self.assertEqual(rig.drive.homing_phase, 0x1400)

    def test_homing_error_takes_the_drive_down(self):
        rig = self.make(homing_fails=True)
        rig.enable, rig.mode = True, 6
        rig.error(ERR['homing'])
        rig.until(lambda r: r.drive.state == SOD, what='way down')
        rig.run(2)  # one to show it, one to believe it
        self.assertEqual(rig.words[-1], 0x0000)

    def test_homing_that_does_not_end_times_out(self):
        rig = self.make(homing_scans=10000)
        rig.enable, rig.mode = True, 6
        n = rig.until(lambda r: r.out['bError'], limit=200, what='homing timeout')
        self.assertEqual(rig.out['nErrorID'], ERR['homing_time'])
        self.assertGreaterEqual(n * CYCLE, 1000)

    def test_bit_4_drops_when_enable_does(self):
        rig = self.make(homing_scans=10000)
        rig.enable, rig.mode = True, 6
        rig.until(lambda r: r.words[-1] == 0x001F, what='bit 4')
        rig.enable = False
        rig.scan()
        self.assertEqual(rig.words[-1] & 0x10, 0)
        rig.at_rest()

    def test_mode_change_in_the_middle_of_homing(self):
        rig = self.make(homing_scans=10000, position=300)
        rig.enable, rig.mode = True, 6
        rig.until(lambda r: r.words[-1] == 0x001F, what='bit 4')
        rig.run(5)
        rig.mode = 8
        rig.valid()
        self.assertEqual(rig.drive.homing_phase, 0x0400)  # interrupted


class Latency(TemplateCase):
    """The statusword reaches the FB one to three cycles late, as over a real bus."""

    def test_scenarios_hold_with_a_late_statusword(self):
        for lag in (1, 2, 3):
            with self.subTest(lag=lag):
                rig = self.running(lag=lag)
                rig.drive.fault()
                rig.error(ERR['drive_fault'])
                rig.run(10)
                rig.pulse_reset()
                rig.valid()
                rig.drive.external_quick_stop()
                rig.error(ERR['quick_stop'])
                rig.until(lambda r: r.drive.state == SOD, what='end of the stop')
                rig.pulse_reset()
                rig.valid()
                rig.mode = 6
                rig.valid()
                rig.mode = 8
                rig.valid()
                rig.enable = False
                rig.at_rest()

    def test_enable_dropped_at_every_scan_of_the_way_up(self):
        # Dropped while T4 is on its way, 0x0000 would arrive in Operation enabled.
        for lag in (0, 1, 2):
            scans = self.running(lag=lag).words.__len__()
            for drop in range(scans + 2):
                with self.subTest(lag=lag, drop=drop):
                    rig = self.make(lag=lag)
                    rig.enable, rig.mode = True, 8
                    rig.run(drop)
                    rig.enable = False
                    rig.at_rest()
                    # A late T4 is stopped with T5: bEnable FALSE is no quick stop.
                    self.assertNotIn('quick_stop_active',
                                     [to for _, to, _ in rig.drive.transitions])

    def test_enable_raised_again_at_every_scan_of_the_way_down(self):
        for lag in (0, 1, 2):
            for again in range(8):
                with self.subTest(lag=lag, again=again):
                    rig = self.running(lag=lag)
                    rig.enable = False
                    rig.run(again)
                    rig.enable = True
                    rig.until(lambda r: r.out['bValid'] or r.out['bError'],
                              what='valid or error')
                    rig.enable = False
                    rig.at_rest()


class StaleWordOnTheWayDown(TemplateCase):
    """The drive drops out while 0x000F is still going out, so that it is back in Operation
    enabled when a late statusword shows the state it dropped to. Every word sent there has
    to be safe in both states. Each drop comes soon after the last change of word and again
    after more than tStateTimeout of holding it: it is the holding that counts, not when
    0x000F first went out."""

    LAGS = (0, 1, 2, 3)
    HELD = 30  # scans, over tStateTimeout

    def goes_down(self, rig):
        mark = len(rig.words)
        rig.error(ERR['left_state'])
        rig.run(30)
        self.assertEqual(rig.drive.state, SOD)
        self.assertEqual(rig.words[-1], 0x0000)
        down = rig.distinct_words(mark)
        if 0x0002 in down:  # once T11 is out, no T5 on top of it
            self.assertNotIn(0x0007, down[down.index(0x0002):])

    def test_drop_to_switched_on_while_running(self):
        for lag, held in product(self.LAGS, (0, self.HELD)):
            with self.subTest(lag=lag, held=held):
                rig = self.running(lag=lag)
                rig.run(held)
                rig.drive.drop('switched_on')
                self.goes_down(rig)

    def test_drop_with_a_mode_bit_held(self):
        # The word is 0x010F then, halt: it is bit 3 that may still land, not one word.
        for lag in self.LAGS:
            with self.subTest(lag=lag):
                rig = self.running(lag=lag, mode=9)
                rig.io['nModeBits'] = 0x0100
                rig.caller = lambda r: r.io.__setitem__('nModeBits', 0x0100)
                rig.run(self.HELD)
                rig.drive.drop('switched_on')
                self.goes_down(rig)

    def test_a_refused_t11_after_the_drop_falls_back_to_t5(self):
        for lag in self.LAGS:
            with self.subTest(lag=lag):
                rig = self.running(lag=lag, refuse=('quick_stop_active',))
                rig.drive.drop('switched_on')
                rig.error(ERR['left_state'])
                rig.until(lambda r: r.drive.state == SOD, what='way down')

    def test_a_drive_that_stays_in_quick_stop_active(self):
        # bEnable falls with the drop still unseen: no error, and a T11 on a drive with
        # 0x605A 5-8 needs bQuickStopStays, bQuickStop or not.
        for lag in (1, 2, 3):
            with self.subTest(lag=lag, flag=True):
                rig = self.running(lag=lag, quick_stop_stays=True,
                                   config={'bQuickStopStays': True})
                rig.drive.drop('switched_on')
                rig.run(lag)
                rig.enable = False
                rig.at_rest()
            with self.subTest(lag=lag, flag=False):
                rig = self.running(lag=lag, quick_stop_stays=True)
                rig.drive.drop('switched_on')
                rig.run(lag)
                rig.enable = False
                rig.run(200)
                self.assertEqual(rig.drive.state, 'quick_stop_active')
                self.assertEqual(rig.words[-1], 0x0002)
                self.assertTrue(rig.out['bBusy'])
                self.assertFalse(rig.out['bError'])

    def test_drop_to_ready_to_switch_on_while_running(self):
        for lag in self.LAGS:
            with self.subTest(lag=lag):
                rig = self.running(lag=lag)
                rig.drive.drop('ready_to_switch_on')
                self.goes_down(rig)

    def test_drop_during_homing(self):
        for lag, held in product(self.LAGS, (0, self.HELD)):
            with self.subTest(lag=lag, held=held):
                rig = self.make(lag=lag, homing_scans=10000)
                rig.enable, rig.mode = True, 6
                rig.until(lambda r: r.words[-1] == 0x001F, what='bit 4')
                rig.run(lag + 2 + held)
                mark = len(rig.words)
                rig.drive.drop('switched_on')
                self.goes_down(rig)
                self.assertIn(0x0002, rig.words[mark:])  # 0x001F had bit 3, not the word 0x000F

    def test_drop_during_a_mode_switch(self):
        for lag in self.LAGS:
            with self.subTest(lag=lag):
                rig = self.running(lag=lag, mode_delay=12)
                rig.mode = 9
                rig.run(3)
                rig.drive.drop('switched_on')
                self.goes_down(rig)

    def test_undecodable_statusword_as_0x000f_goes_out(self):
        # The Unknown branch sends 0x0007, the late statusword then shows Switched on, and
        # the drive, which wants a steady word, takes 0x000F just before that.
        for lag in self.LAGS:
            for at in range(1, 6):
                with self.subTest(lag=lag, at=at):
                    rig = self.make(lag=lag, settle=3)
                    rig.enable, rig.mode = True, 8
                    rig.until(lambda r: r.words[-1] == 0x000F, what='T4')
                    rig.run(at - 1)
                    rig.drive.override_sw = 0x0005
                    rig.scan()
                    rig.drive.override_sw = None
                    rig.until(lambda r: r.drive.state == SOD and r.out['bError'],
                              what='way down')


class NoBit2(TemplateCase):
    """A drive with no quick stop that reads controlword bit 2 as 1, so that 0x0002 is
    Shutdown: the way down must still end. What a real one does with the bit is not known."""

    LAGS = StaleWordOnTheWayDown.LAGS

    def test_way_down_from_each_state(self):
        for lag, start in product(self.LAGS, (OE, 'switched_on', 'ready_to_switch_on')):
            with self.subTest(lag=lag, start=start):
                if start == OE:
                    rig = self.running(lag=lag, ignores_bit_2=True)
                    rig.enable = False
                else:
                    rig = self.make(lag=lag, state=start, ignores_bit_2=True)
                n = rig.until(lambda r: r.drive.state == SOD, what='way down')
                self.assertGreaterEqual(n * CYCLE, 200)  # tStateTimeout
                rig.at_rest()
                self.assertFalse(rig.out['bError'])
                rig.enable, rig.mode = True, 8
                rig.valid()

    def test_enable_dropped_at_every_scan_of_the_way_up(self):
        # 0x0002 lifts it out of Switch on disabled as Shutdown: with a late statusword,
        # 0x0002 and 0x0000 can chase each other, but only until tStateTimeout is up.
        for lag in self.LAGS:
            scans = len(self.running(lag=lag, ignores_bit_2=True).words)
            for drop in range(scans + 2):
                with self.subTest(lag=lag, drop=drop):
                    rig = self.make(lag=lag, ignores_bit_2=True)
                    rig.enable, rig.mode = True, 8
                    rig.run(drop)
                    rig.enable = False
                    rig.run(30)  # tStateTimeout, and the lag
                    self.assertEqual(rig.drive.state, SOD)
                    self.assertEqual(rig.words[-5:], [0x0000] * 5)

    def test_drop_out_while_0x000f_goes_out(self):
        for lag, state in product(self.LAGS, ('switched_on', 'ready_to_switch_on')):
            with self.subTest(lag=lag, state=state):
                rig = self.running(lag=lag, ignores_bit_2=True)
                rig.drive.drop(state)
                rig.error(ERR['left_state'])
                rig.until(lambda r: r.drive.state == SOD, what='way down')

    def test_a_stop_longer_than_tstatetimeout_does_not_chase(self):
        # 0x0002 on the first scan of a state, with no 0x000F left to land, is Shutdown here:
        # it and 0x0000 chase each other for ever, each change re-arming the step's timeout.
        for lag in self.LAGS:
            with self.subTest(lag=lag):
                rig = self.running(lag=lag, ignores_bit_2=True)
                mark = len(rig.drive.transitions)
                rig.drive.refuse = ('switched_on',)
                rig.enable = False
                rig.run(30)
                rig.drive.refuse = ()
                rig.run(100)
                self.assertEqual(rig.drive.state, SOD)
                self.assertLessEqual(len(rig.drive.transitions[mark:]), 3)

    def test_quick_stop_is_an_error_and_ends_at_rest(self):
        for lag, pulse in product(self.LAGS, (False, True)):
            with self.subTest(lag=lag, pulse=pulse):
                rig = self.running(lag=lag, ignores_bit_2=True)
                rig.quick_stop = True
                rig.scan()
                rig.quick_stop = not pulse
                rig.error(ERR['no_quick_stop'])
                rig.until(lambda r: r.drive.state == SOD, what='way down')


class BadStatusword(TemplateCase):
    """One scan of inputs that are not the drive's, as it stands in a state where 0x0000 would
    do harm. The word reaches the FB `lag` scans later, and the scans after it are good."""

    LAGS = StaleWordOnTheWayDown.LAGS
    FAULT = (0x0009, 0x000B, 0x000D, 0x000F)
    AT_REST = (0x0240, 0x0250, 0x0260)
    DOWN = (0x0021, 0x0023)

    def bad_scan(self, rig, word):
        rig.drive.override_sw = word
        rig.scan()
        rig.drive.override_sw = None

    def slow_stop(self, lag):
        """bEnable FALSE, and a drive still in Operation enabled past tStateTimeout: 0x0007
        has been out for that long, so that fbEnableWordOff says nothing here."""
        rig = self.running(lag=lag)
        rig.drive.refuse = ('switched_on', SOD)
        rig.enable = False
        rig.run(30)
        self.assertEqual(rig.drive.state, OE)
        return rig

    def test_running_with_the_target_moving(self):
        for lag, word in product(self.LAGS, self.FAULT + self.AT_REST):
            with self.subTest(lag=lag, word=hex(word)):
                rig = self.running(lag=lag)
                rig.caller = ramp(50)
                rig.run(10)
                self.bad_scan(rig, word)
                rig.until(lambda r: r.out['bError'], what='the error')
                rig.until(lambda r: r.drive.state == SOD, what='way down')

    def test_running_with_another_set_point_moving(self):
        for lag, (mode, name), word in product(
                self.LAGS, ((9, 'nTargetVelocity'), (10, 'nTargetTorque')),
                self.FAULT + self.AT_REST + self.DOWN):
            with self.subTest(lag=lag, mode=mode, word=hex(word)):
                rig = self.running(lag=lag, mode=mode)
                rig.caller = lambda r, n=name: r.io.__setitem__(n, r.io[n] + 5)
                rig.run(10)
                self.bad_scan(rig, word)
                rig.until(lambda r: r.out['bError'], what='the error')
                rig.until(lambda r: r.drive.state == SOD, what='way down')

    def test_the_word_kept_has_only_bits_0_to_2(self):
        # Halt held: neither bit 3 nor the caller's bits outlive bValid.
        for lag, word in product(self.LAGS, self.FAULT + self.AT_REST):
            with self.subTest(lag=lag, word=hex(word)):
                rig = self.running(lag=lag, mode=9)
                rig.caller = lambda r: r.io.__setitem__('nModeBits', 0x0100)
                rig.run(5)
                self.assertEqual(rig.words[-1], 0x010F)
                mark = len(rig.words)
                self.bad_scan(rig, word)
                rig.run(lag)
                self.assertTrue(rig.out['bError'])
                self.assertEqual(rig.words[mark + lag], 0x0007)  # the scan the FB saw it

    def test_as_0x000f_goes_out(self):
        # The shape that found it: a drive that wants a steady word takes T4 late.
        for lag, at, word in product(self.LAGS, range(1, 6), self.FAULT + self.AT_REST):
            with self.subTest(lag=lag, at=at, word=hex(word)):
                rig = self.make(lag=lag, settle=3)
                rig.enable, rig.mode = True, 8
                rig.until(lambda r: r.words[-1] == 0x000F, what='T4')
                rig.run(at - 1)
                self.bad_scan(rig, word)
                rig.until(lambda r: r.drive.state == SOD and r.out['bError'], what='way down')

    def test_in_a_stop_longer_than_tstatetimeout(self):
        for lag, word in product(self.LAGS, self.FAULT + self.AT_REST + self.DOWN):
            with self.subTest(lag=lag, word=hex(word)):
                rig = self.slow_stop(lag)
                self.bad_scan(rig, word)
                rig.run(lag + 5)
                self.assertEqual(rig.drive.state, OE)  # no T11 on top of the T5 either

    def test_in_a_quick_stop_longer_than_tstatetimeout(self):
        # 0x0000 there is T12: the motor coasts. 0x0002 has been out for over tStateTimeout.
        for lag, asked, word in product(self.LAGS, (True, False),
                                        self.FAULT + self.AT_REST + self.DOWN):
            with self.subTest(lag=lag, asked=asked, word=hex(word)):
                rig = self.running(lag=lag, qs_ramp=100)
                if asked:
                    rig.quick_stop = True
                else:
                    rig.drive.external_quick_stop()
                    rig.enable = False
                rig.run(lag + 30)
                self.bad_scan(rig, word)
                rig.run(lag + 5)
                self.assertEqual(rig.words[-1], 0x0002)

    def test_in_an_error_with_the_drive_still_enabled(self):
        for lag, word in product(self.LAGS, self.AT_REST + self.DOWN):
            with self.subTest(lag=lag, word=hex(word)):
                rig = self.slow_stop(lag)
                rig.error(ERR['stop'])
                self.bad_scan(rig, word)
                rig.run(lag + 5)
                self.assertEqual(rig.drive.state, OE)

    def test_after_a_refused_t11_with_the_drive_still_enabled(self):
        for lag, word in product(self.LAGS, self.AT_REST):
            with self.subTest(lag=lag, word=hex(word)):
                rig = self.running(lag=lag)
                rig.drive.refuse = ('quick_stop_active', 'switched_on', SOD)
                rig.quick_stop = True
                rig.error(ERR['no_quick_stop'])
                rig.run(lag + 2)
                self.bad_scan(rig, word)
                rig.run(lag + 5)
                self.assertEqual(rig.drive.state, OE)

    def test_a_pulsed_quick_stop_stays_held(self):
        # bQuickStop is FALSE by then: one scan of at rest must not release the latch.
        for lag, word in product(self.LAGS, self.AT_REST):
            with self.subTest(lag=lag, word=hex(word)):
                rig = self.running(lag=lag, qs_ramp=100)
                rig.quick_stop, rig.enable = True, False
                rig.scan()
                rig.quick_stop = False
                rig.run(lag + 5)
                self.bad_scan(rig, word)
                rig.run(lag + 2)
                rig.enable = True
                rig.run(150)
                self.assertEqual(rig.drive.state, SOD)
                self.assertEqual(rig.words[-1], 0x0000)

    def test_enable_raised_on_the_scan(self):
        # Switch on disabled for one scan is no reason to send T2: on this drive it is T8.
        for lag, word in product(self.LAGS, self.AT_REST):
            with self.subTest(lag=lag, word=hex(word)):
                rig = self.slow_stop(lag)
                rig.enable = True
                mark = len(rig.words)
                self.bad_scan(rig, word)
                rig.run(lag + 5)
                self.assertNotIn(0x0006, rig.words[mark:])

    def test_a_reset_on_the_scan(self):
        # A reset begins with 0x0000. It is for a drive seen in Fault twice.
        for lag, word in product(self.LAGS, self.FAULT):
            with self.subTest(lag=lag, word=hex(word)):
                rig = self.slow_stop(lag)
                rig.error(ERR['stop'])
                for n in range(lag + 1):
                    rig.drive.override_sw = None if n else word
                    rig.reset = n == lag
                    rig.scan()
                rig.drive.override_sw, rig.reset = None, False
                rig.run(lag + 5)

    def test_in_a_reset_it_spends_no_attempt(self):
        # The drive is still in Fault: every attempt still goes out, the only one included.
        # Two scans: in a fast task, one bad frame is two scans.
        for lag, step, word, scans, attempts in product(
                self.LAGS, ('ResetLow', 'ResetPause'), self.AT_REST + self.DOWN, (1, 2), (1, 3)):
            if attempts == 1 and step == 'ResetPause':
                continue  # one attempt has no pause
            with self.subTest(lag=lag, step=step, word=hex(word), scans=scans, attempts=attempts):
                rig = self.persistent_fault(lag, config={'nResetAttempts': attempts})
                mark = len(rig.words)
                self.in_step(rig, step)
                for _ in range(scans):
                    self.bad_scan(rig, word)
                rig.error(ERR['reset_failed'])
                self.assertEqual(len(rig.edges_of_bit_7(mark)), attempts)

    def test_a_word_that_stays_in_fault(self):
        # No 0x0000 from there until a reset: the README says what a reset does then.
        for lag, word in product(self.LAGS, self.FAULT):
            with self.subTest(lag=lag, word=hex(word)):
                rig = self.slow_stop(lag)
                rig.drive.override_sw = word
                rig.run(lag + 30)
                rig.drive.override_sw = None
                self.assertEqual(rig.words[-1], 0x0007)

    def test_a_real_drop_still_ends_in_0x0000(self):
        for lag in self.LAGS:
            with self.subTest(lag=lag):
                rig = self.running(lag=lag)
                rig.drive.drop(SOD)
                rig.until(lambda r: r.out['bError'], what='the error')
                rig.run(lag + 2)
                self.assertEqual(rig.words[-1], 0x0000)


class Errors(TemplateCase):

    def test_transitions_the_drive_refuses_time_out(self):
        for state, code in (('ready_to_switch_on', 'shutdown'), ('switched_on', 'switch_on'),
                            (OE, 'enable')):
            with self.subTest(refused=state):
                rig = self.make(refuse=(state,))
                rig.enable, rig.mode = True, 8
                n = rig.error(ERR[code])
                self.assertGreaterEqual(n * CYCLE, 200)
                rig.at_rest()

    def test_drive_that_drops_out_is_not_enabled_again_without_reset(self):
        rig = self.running()
        rig.drive.drop(SOD)
        rig.error(ERR['left_state'])
        rig.run(50)
        self.assertEqual(rig.drive.state, SOD)
        self.assertEqual(rig.words[-1], 0x0000)
        rig.pulse_reset()
        rig.valid()

    def test_drive_that_never_boots(self):
        rig = self.make(state='not_ready_to_switch_on', boot_scans=10000)
        rig.enable, rig.mode = True, 8
        rig.error(ERR['not_ready'])

    def test_statusword_that_decodes_to_nothing(self):
        rig = self.running()
        rig.drive.override_sw = 0x0005
        rig.error(ERR['statusword'])
        self.assertEqual(rig.words[-1], 0x0007)  # the last word, less enable operation
        rig.pulse_reset()
        self.assertTrue(rig.out['bError'])  # no reset while the word means nothing
        rig.drive.override_sw = None
        rig.until(lambda r: r.drive.state == SOD, what='way down')

    def test_statusword_0000_while_running(self):
        # Inputs that read 0 (a bus restart, a missing copy) are not Not ready.
        rig = self.running()
        rig.drive.override_sw = 0x0000
        rig.error(ERR['statusword'])
        rig.run(5)
        rig.drive.override_sw = None
        rig.until(lambda r: r.drive.state == SOD, what='way down')

    def test_defaults_of_the_config(self):
        rig = Rig(SimDrive(refuse=('switched_on',)))
        self.rigs.append(rig)
        for name in FAST:
            rig.config[name] = Struct(PROGRAM, 'ST_Cia402Config')[name]
        rig.enable, rig.mode = True, 8
        n = rig.until(lambda r: r.out['bError'], limit=400, what='timeout')
        self.assertGreaterEqual(n * CYCLE, 2000)  # T#2S, plus the scans to get there
        self.assertLess(n * CYCLE, 2100)


class Interpreter(unittest.TestCase):
    """The subset refuses what it does not cover, rather than guessing."""

    def run_body(self, body, decls='x : WORD; b : BOOL;'):
        program = Program(f'FUNCTION_BLOCK FB_T\nVAR\n{decls}\nEND_VAR\n{body}\n'
                          f'END_FUNCTION_BLOCK\n')
        fb = program.instance('FB_T')
        fb.scan(0)
        return fb

    def test_bool_and_word_do_not_mix(self):
        with self.assertRaises(StError):
            self.run_body('b := b AND x;')

    def test_not_on_an_integer_is_refused(self):
        with self.assertRaises(StError):
            self.run_body('x := NOT x;')

    def test_condition_must_be_bool(self):
        with self.assertRaises(StError):
            self.run_body('IF x THEN b := TRUE; END_IF')

    def test_words_wrap(self):
        self.assertEqual(self.run_body('x := 16#FFFF + 2;')['x'], 1)

    def test_outside_the_subset(self):
        for text in ('WHILE b DO b := FALSE; END_WHILE', 'x := SHL(x, 1);',
                     'FOR x := 1 TO 3 DO END_FOR', '{IF defined(X)} b := TRUE; {END_IF}'):
            with self.subTest(text=text), self.assertRaises(StError):
                self.run_body(text)

    def test_a_name_declared_twice_is_refused(self):
        with self.assertRaises(StError):
            self.run_body(';', 'x : WORD; x : BOOL;')

    def test_precedence(self):
        self.assertTrue(self.run_body('b := 1 + 2 * 3 = 7 AND NOT FALSE;')['b'])


# One edit per rule, each breaking it in the template's text, and the scenario that
# must then fail. The edit must match the template exactly once.
BROKEN_RULES = {
    'quick stop cut with 0x0000': (
        'stDrive.nControlword := 16#0002;   // let it finish',
        'stDrive.nControlword := 16#0000;   // let it finish',
        QuickStop, 'test_external_quick_stop_is_left_to_finish'),
    'quick stop left on a timer': (
        '                IF fbStandstill.Q THEN',
        '                IF fbStandstill.Q OR fbStepTimer.Q THEN',
        QuickStop, 'test_jitter_without_a_band_holds_the_quick_stop'),
    'quick stop left without bQuickStopStays': (
        'fbStandstill(IN := stConfig.bQuickStopStays\n',
        'fbStandstill(IN := TRUE\n',
        QuickStop, 'test_quick_stop_is_not_cut_when_0x6064_is_not_copied'),
    'T16 out of a quick stop': (
        'stDrive.nControlword := 16#0002;   // let it finish',
        'stDrive.nControlword := 16#000F;   // let it finish',
        QuickStop, 'test_quick_stop_that_stays_is_left_at_standstill'),
    'commanded quick stop left on a timer': (
        'IF bAtRest OR fbStandstill.Q THEN',
        'IF bAtRest OR fbStandstill.Q OR fbStepTimer.Q THEN',
        CommandedQuickStop, 'test_a_ramp_longer_than_the_stop_timeout_is_no_error'),
    'the ramp of a commanded quick stop timed out': (
        'fbQuickStopTimer(IN := bQuickStopHeld AND NOT bAtRest\n'
        '                       AND (eDriveState <> E_Cia402State.QuickStopActive),',
        'fbQuickStopTimer(IN := bQuickStopHeld AND NOT bAtRest,',
        CommandedQuickStop, 'test_a_ramp_longer_than_the_stop_timeout_is_no_error'),
    "the last step's timer taken for the quick stop's": (
        '        ELSIF fbQuickStopTimer.Q THEN',
        '        ELSIF fbStepTimer.Q THEN',
        CommandedQuickStop, 'test_a_long_run_before_it_is_no_timeout'),
    'commanded quick stop sent as T5': (
        'stDrive.nControlword := 16#0002;   // T11, held',
        'stDrive.nControlword := 16#0007;   // T11, held',
        CommandedQuickStop, 'test_t11_goes_out_at_once_and_is_held'),
    'T9 to a T4 still on its way': (
        'IF bAtRest OR fbStandstill.Q THEN',
        'IF bAtRest OR fbStandstill.Q OR (eDriveState = E_Cia402State.SwitchedOn) THEN',
        CommandedQuickStop, 'test_raised_at_every_scan_of_the_way_up'),
    'quick stop taken only from Running': (
        'ELSIF bQuickStopHeld AND NOT bResetting THEN',
        'ELSIF bQuickStopHeld AND (eStep = E_Cia402Step.Running) THEN',
        CommandedQuickStop, 'test_raised_at_every_scan_of_the_way_up'),
    'fault reset cut off by a quick stop': (
        'ELSIF bQuickStopHeld AND NOT bResetting THEN',
        'ELSIF bQuickStopHeld THEN',
        CommandedQuickStop, 'test_raised_at_every_scan_of_a_fault_reset'),
    'restarted by the end of the quick stop': (
        'ELSIF bAtRest AND NOT bEnable THEN',
        'ELSIF bAtRest THEN',
        CommandedQuickStop, 'test_line_stop_restarts_only_once_the_line_is_ok_and_run_is_set_again'),
    'busy while held down': (
        '          AND ((bEnable AND (eStep <> E_Cia402Step.QuickStop)) OR NOT bAtRest);',
        '          AND (bEnable OR NOT bAtRest);',
        CommandedQuickStop, 'test_line_stop_restarts_only_once_the_line_is_ok_and_run_is_set_again'),
    'quick stop not sent to an enabled drive in Error': (
        '                IF (bQuickStopHeld AND NOT fbQuickStopTimer.Q)\n',
        '                IF FALSE\n',
        CommandedQuickStop, 'test_in_an_error_an_enabled_drive_still_gets_t11'),
    'no way back to T5 from a refused T11': (
        '                IF (bQuickStopHeld AND NOT fbQuickStopTimer.Q)\n',
        '                IF bQuickStopHeld\n',
        CommandedQuickStop, 'test_a_drive_that_refuses_t11_is_taken_down_with_t5'),
    'T5 for a quick stop asked with an undecodable statusword': (
        'may be a bad one.\n                IF bQuickStopHeld AND NOT fbQuickStopTimer.Q THEN',
        'may be a bad one.\n                IF FALSE THEN',
        CommandedQuickStop, 'test_an_undecodable_statusword_gets_0x0002_as_well'),
    'quick stop forgotten in an error': (
        'ELSIF bQuickStopHeld AND NOT bResetting THEN',
        'ELSIF bQuickStop AND NOT bResetting THEN',
        CommandedQuickStop, 'test_a_fault_while_held_down_does_not_release_it'),
    'quick stop lost during a fault reset': (
        'IF bQuickStop THEN\n    bQuickStopHeld := TRUE;',
        'IF bQuickStop AND NOT bResetting THEN\n    bQuickStopHeld := TRUE;',
        CommandedQuickStop, 'test_raised_at_every_scan_of_a_fault_reset'),
    'T9 from Operation enabled': (
        'stDrive.nControlword := 16#0007;   // T5, stops as 0x605C',
        'stDrive.nControlword := 16#0000;   // T5, stops as 0x605C',
        Disabling, 'test_way_down_from_operation_enabled_as_the_planner_says'),
    'Enable operation straight from Switch on disabled': (
        'stDrive.nControlword := 16#0006;   // T2',
        'stDrive.nControlword := 16#000F;   // T2',
        Enabling, 'test_from_each_state_as_the_planner_says'),
    'bit 7 never released': (
        'IF (eDriveState <> E_Cia402State.Fault) OR fbStepTimer.Q THEN',
        'IF eDriveState <> E_Cia402State.Fault THEN',
        FaultReset, 'test_failed_resets_release_bit_7_every_time'),
    'bit 7 with the enable bits': (
        '            stDrive.nControlword := 16#0080;\n',
        '            stDrive.nControlword := 16#008F;\n',
        FaultReset, 'test_fault_while_running_then_reset'),
    'reset outside Fault': (
        '            IF eDriveState = E_Cia402State.Fault THEN\n                nErrorID    := 0;',
        '            IF TRUE THEN\n                nErrorID    := 0;',
        FaultReset, 'test_reset_is_never_sent_to_a_drive_not_in_fault'),
    'reset on a level, not an edge': (
        'ELSIF fbResetTrig.Q THEN\n    bResetRequest := TRUE;',
        'ELSIF bReset THEN\n    bResetRequest := TRUE;',
        FaultReset, 'test_level_reset_resets_once'),
    'no pause between reset attempts': (
        'tStepLimit := stConfig.tResetPause;',
        'tStepLimit := cResetSettle;',
        FaultReset, 'test_attempts_are_paused'),
    'reset attempts not counted afresh': (
        '                nResetCount := 0;\n',
        '',
        FaultReset, 'test_reset_attempts_restart_on_each_reset'),
    'reset asked in Fault reaction active dropped': (
        '        IF bResetRequest AND NOT bDriveMoved THEN',
        '        IF bResetRequest AND NOT bDriveMoved AND fbResetTrig.Q THEN',
        FaultReset, 'test_reset_asked_in_fault_reaction_active_is_kept'),
    'stale homing result taken': (
        '        ELSIF bHomingRunSeen\n              AND ((stDrive.nStatusword AND 16#3400)',
        '        ELSIF TRUE\n              AND ((stDrive.nStatusword AND 16#3400)',
        Homing, 'test_result_of_an_earlier_run_is_not_taken_for_this_one'),
    'stale homing error taken': (
        '        ELSIF bHomingRunSeen\n              AND ((stDrive.nStatusword AND 16#2000)',
        '        ELSIF TRUE\n              AND ((stDrive.nStatusword AND 16#2000)',
        Homing, 'test_retry_after_a_homing_error'),
    '0x6060 in the same scan as the set-point': (
        '        IF bSetModeLastScan THEN',
        '        IF TRUE THEN',
        ModeSwitch, 'test_new_modes_set_point_is_made_safe_first'),
    "new mode's velocity not made safe": (
        '            3, 9:\n                stDrive.nTargetVelocity := 0;',
        '            3, 9:\n                ;',
        ModeSwitch, 'test_new_modes_set_point_is_made_safe_first'),
    'mode not confirmed on 0x6061': (
        '              AND (stDrive.nModesDisplay = nMode)\n        THEN\n            IF eDriveState',
        '        THEN\n            IF eDriveState',
        ModeSwitch, 'test_switch_while_enabled_is_confirmed_on_6061'),
    'mode change during T4 not seen': (
        '            ELSIF (nMode <> stDrive.nModesOfOperation)\n                  OR (nMode <> '
        'stDrive.nModesDisplay)\n            THEN\n                eStep := E_Cia402Step.SetMode;\n'
        '            ELSIF nMode = 6 THEN',
        '            ELSIF nMode = 6 THEN',
        ModeSwitch, 'test_mode_change_during_t4_goes_back_to_set_mode'),
    'drop during a switch enabled again': (
        '        ELSIF bDriveMoved\n              OR ((eDriveState',
        '        ELSIF FALSE\n              OR ((eDriveState',
        ModeSwitch, 'test_drop_to_switched_on_during_a_switch_is_an_error'),
    'target not held at actual before T4': (
        '    stDrive.nTargetPosition := stDrive.nPositionActual;\n    stDrive.nTargetVelocity := 0;',
        '    stDrive.nTargetVelocity := 0;',
        Enabling, 'test_csp_target_follows_actual_until_valid'),
    'velocity not held at 0 before T4': (
        '    stDrive.nTargetVelocity := 0;\n    stDrive.nTargetTorque   := 0;',
        '    stDrive.nTargetTorque   := 0;',
        Enabling, 'test_csv_and_cst_enable_with_zero_set_points'),
    'torque not held at 0 before T4': (
        '    stDrive.nTargetTorque   := 0;\n    stDrive.nModeBits       := 0;',
        '    stDrive.nModeBits       := 0;',
        Enabling, 'test_csv_and_cst_enable_with_zero_set_points'),
    'set-points pulled back while enabled': (
        'ELSIF (eDriveState <> E_Cia402State.OperationEnabled)\n      AND (eDriveState <> '
        'E_Cia402State.QuickStopActive)\nTHEN',
        'ELSIF TRUE THEN',
        Disabling, 'test_set_points_are_held_on_the_way_down'),
    'stale mode bits kept': (
        '    stDrive.nModeBits       := 0;\n',
        '',
        Enabling, 'test_stale_mode_bits_are_cleared_before_valid'),
    'caller bits on the first valid scan': (
        'IF (nMode = 6) OR NOT bRunningLastScan THEN',
        'IF nMode = 6 THEN',
        Enabling, 'test_mode_bits_pass_only_while_valid'),
    'mode bits before valid': (
        '        stDrive.nControlword := 16#0006;   // T2',
        '        stDrive.nControlword := 16#0006 OR stDrive.nModeBits;   // T2',
        Enabling, 'test_mode_bits_pass_only_while_valid'),
    'way down abandons a T4 on its way': (
        '        ELSIF NOT bEnable THEN\n            eStep := E_Cia402Step.AbortEnable;',
        '        ELSIF NOT bEnable THEN\n            eStep := E_Cia402Step.Disabled;',
        Latency, 'test_enable_dropped_at_every_scan_of_the_way_up'),
    'T9 from a stale Switched on': (
        '                    stDrive.nControlword := 16#0002;\n                END_IF\n'
        '            E_Cia402State.Fault,',
        '                    stDrive.nControlword := 16#0000;\n                END_IF\n'
        '            E_Cia402State.Fault,',
        StaleWordOnTheWayDown, 'test_drop_to_switched_on_while_running'),
    "tStopTimeout taken for 0x0002's way out": (
        '                IF fbEnableWordOff.Q AND NOT bDriveMoved THEN\n'
        '                    stDrive.nControlword := 16#0000;',
        '                IF fbStepTimer.Q THEN\n'
        '                    stDrive.nControlword := 16#0000;',
        NoBit2, 'test_way_down_from_each_state'),
    'no way out of 0x0002 for a drive that ignores bit 2': (
        '                IF fbEnableWordOff.Q AND NOT bDriveMoved THEN\n'
        '                    stDrive.nControlword := 16#0000;',
        '                IF FALSE THEN\n'
        '                    stDrive.nControlword := 16#0000;',
        NoBit2, 'test_way_down_from_each_state'),
    'the time since 0x000F never re-armed': (
        'fbEnableWordOff(IN := (stDrive.nControlword AND 16#0008) = 0,',
        'fbEnableWordOff(IN := TRUE,',
        StaleWordOnTheWayDown, 'test_drop_to_switched_on_while_running'),
    'only the word 0x000F counted as an enable word': (
        'fbEnableWordOff(IN := (stDrive.nControlword AND 16#0008) = 0,',
        'fbEnableWordOff(IN := stDrive.nControlword <> 16#000F,',
        StaleWordOnTheWayDown, 'test_drop_during_homing'),
    'T5 on top of a T11 that the late statusword has not shown': (
        '                   OR ((stDrive.nControlword = 16#0002)\n'
        '                       AND NOT fbEnableWordOff.Q)\n',
        '',
        StaleWordOnTheWayDown, 'test_drop_to_switched_on_while_running'),
    "0x0002's way out re-armed by the state the drive shows": (
        'fbEnableWordOff(IN := (stDrive.nControlword AND 16#0008) = 0,',
        'fbEnableWordOff(IN := ((stDrive.nControlword AND 16#0008) = 0) AND NOT bAtRest,',
        NoBit2, 'test_enable_dropped_at_every_scan_of_the_way_up'),
    'one 0x6F mask for every state': (
        'IF (stDrive.nStatusword AND 16#004F) = 16#0000 THEN',
        'IF (stDrive.nStatusword AND 16#006F) = 16#0000 THEN',
        Decode, 'test_every_statusword_pattern_against_the_decoder'),
    'a statusword of 0 taken for Not ready': (
        'ELSIF bDriveSeen AND (eDriveState = E_Cia402State.NotReadyToSwitchOn) THEN',
        'ELSIF FALSE THEN',
        Errors, 'test_statusword_0000_while_running'),
    'undecodable statusword keeps the drive enabled': (
        '                ELSE\n'
        '                    stDrive.nControlword := stDrive.nControlword AND 16#0007;',
        '                ELSE\n'
        '                    ;',
        Errors, 'test_statusword_that_decodes_to_nothing'),
    'one scan of Fault gets 0x0000': (
        '            E_Cia402State.Fault, E_Cia402State.FaultReactionActive,\n'
        '            E_Cia402State.Unknown:',
        '            E_Cia402State.Fault, E_Cia402State.FaultReactionActive:\n'
        '                stDrive.nControlword := 16#0000;\n'
        '            E_Cia402State.Unknown:',
        BadStatusword, 'test_running_with_the_target_moving'),
    'one scan of at rest gets 0x0000': (
        '            IF bDriveMoved THEN\n',
        '            IF FALSE THEN\n',
        BadStatusword, 'test_running_with_the_target_moving'),
    'one scan of Switched on gets 0x0000 in a long stop': (
        'IF fbEnableWordOff.Q AND NOT bDriveMoved THEN',
        'IF fbEnableWordOff.Q THEN',
        BadStatusword, 'test_in_a_stop_longer_than_tstatetimeout'),
    'one scan of at rest cuts a commanded quick stop': (
        'bAtRest := NOT bDriveMoved\n           AND ((eDriveState',
        'bAtRest := TRUE\n           AND ((eDriveState',
        BadStatusword, 'test_in_a_quick_stop_longer_than_tstatetimeout'),
    'one scan of at rest starts T2': (
        'ELSIF bEnable AND NOT bDriveMoved\n',
        'ELSIF bEnable\n',
        BadStatusword, 'test_enable_raised_on_the_scan'),
    'one scan of at rest releases a quick stop': (
        'bAtRest := NOT bDriveMoved\n           AND ((eDriveState',
        'bAtRest := TRUE\n           AND ((eDriveState',
        BadStatusword, 'test_a_pulsed_quick_stop_stays_held'),
    '0x0002 chasing 0x0000 on the first scan of a state': (
        '                ELSIF fbEnableWordOff.Q THEN\n'
        '                    stDrive.nControlword := stDrive.nControlword AND 16#0007;\n',
        '',
        NoBit2, 'test_a_stop_longer_than_tstatetimeout_does_not_chase'),
    'set-point not made safe on the first scan of Operation enabled': (
        '   OR (bDriveMoved AND (eStep <> E_Cia402Step.SetMode))\n',
        '   OR bDriveMoved\n',
        ModeSwitch, 'test_change_on_the_scan_operation_enabled_shows_is_still_made_safe_first'),
    'the word kept at rest keeps bit 3': (
        '            IF bDriveMoved THEN\n'
        '                stDrive.nControlword := stDrive.nControlword AND 16#0007;',
        '            IF bDriveMoved THEN\n'
        '                stDrive.nControlword := stDrive.nControlword AND 16#000F;',
        BadStatusword, 'test_the_word_kept_has_only_bits_0_to_2'),
    'one scan of at rest gets 0x0000 with a quick stop held': (
        '            IF bDriveMoved THEN\n',
        '            IF bDriveMoved AND NOT bQuickStopHeld THEN\n',
        BadStatusword, 'test_after_a_refused_t11_with_the_drive_still_enabled'),
    'one scan of Switched on gets 0x0000 in an error': (
        'IF fbEnableWordOff.Q AND NOT bDriveMoved THEN',
        'IF fbEnableWordOff.Q AND NOT (bDriveMoved AND (eStep = E_Cia402Step.Disabled)) THEN',
        BadStatusword, 'test_in_an_error_with_the_drive_still_enabled'),
    'one scan of another state zeroes velocity or torque': (
        '   OR (bDriveMoved AND (eStep <> E_Cia402Step.SetMode))\n',
        '',
        BadStatusword, 'test_running_with_another_set_point_moving'),
    'one scan of Fault starts a reset': (
        'IF bResetRequest AND NOT bDriveMoved THEN',
        'IF bResetRequest THEN',
        BadStatusword, 'test_a_reset_on_the_scan'),
    'one scan of another state steps the target': (
        '   OR (bDriveMoved AND (eStep <> E_Cia402Step.SetMode))\n',
        '',
        BadStatusword, 'test_running_with_the_target_moving'),
    'drop out enabled again without reset': (
        '            nErrorID := cErrLeftState;\n            eStep    := E_Cia402Step.Error;\n'
        '        ELSIF (nMode <> stDrive.nModesOfOperation)\n              OR (nMode <> '
        'stDrive.nModesDisplay)\n        THEN\n            eStep := E_Cia402Step.SetMode;\n'
        '        END_IF\n\n    E_Cia402Step.ResetLow, E_Cia402Step.ResetPause:',
        '            eStep    := E_Cia402Step.Disabled;\n'
        '        ELSIF (nMode <> stDrive.nModesOfOperation)\n              OR (nMode <> '
        'stDrive.nModesDisplay)\n        THEN\n            eStep := E_Cia402Step.SetMode;\n'
        '        END_IF\n\n    E_Cia402Step.ResetLow, E_Cia402Step.ResetPause:',
        Errors, 'test_drive_that_drops_out_is_not_enabled_again_without_reset'),
    'a drive out of Fault left waiting in the reset': (
        '            ELSIF eDriveState = E_Cia402State.SwitchOnDisabled THEN\n'
        '                nErrorID := 0;\n'
        '                eStep    := E_Cia402Step.Disabled;\n'
        '            ELSIF eDriveState <> E_Cia402State.FaultReactionActive THEN\n'
        '                nErrorID := cErrLeftState;\n'
        '                eStep    := E_Cia402Step.Error;\n'
        '            END_IF\n        END_IF\n\n    E_Cia402Step.ResetEdge:',
        '            END_IF\n        END_IF\n\n    E_Cia402Step.ResetEdge:',
        FaultReset, 'test_a_drive_that_leaves_fault_by_itself_in_the_reset'),
    'a short bad word out of Fault ends the reset': (
        '        IF fbStepTimer.Q THEN\n            IF eDriveState = E_Cia402State.Fault THEN\n',
        '        IF fbStepTimer.Q OR NOT bDriveMoved THEN\n'
        '            IF eDriveState = E_Cia402State.Fault THEN\n',
        BadStatusword, 'test_in_a_reset_it_spends_no_attempt'),
    'Fault reaction active taken for out of Fault in the reset': (
        '            ELSIF eDriveState <> E_Cia402State.FaultReactionActive THEN\n',
        '            ELSE\n',
        FaultReset, 'test_fault_reaction_active_in_the_reset_waits_for_fault'),
}


class BrokenRules(unittest.TestCase):
    """Every rule broken on purpose makes its scenario fail."""

    def test_each_broken_rule_is_caught(self):
        global PROGRAM
        try:
            for rule, (old, new, case, test) in BROKEN_RULES.items():
                with self.subTest(rule=rule):
                    self.assertEqual(ST_TEXT.count(old), 1, 'the edit no longer applies')
                    PROGRAM = Program(ST_TEXT.replace(old, new))
                    result = unittest.TextTestRunner(stream=io.StringIO()).run(case(test))
                    self.assertFalse(result.wasSuccessful(), f'{case.__name__}.{test} '
                                                             f'still passes')
        finally:
            PROGRAM = Program(ST_TEXT)


# --- The files -----------------------------------------------------------------------

BOM = b'\xef\xbb\xbf'
GUID = re.compile(r'\{[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}\}')
TWINCAT = {'FB_Cia402Axis.TcPOU': 'POU', 'E_Cia402State.TcDUT': 'DUT',
           'E_Cia402Step.TcDUT': 'DUT', 'ST_Cia402Drive.TcDUT': 'DUT',
           'ST_Cia402Config.TcDUT': 'DUT'}


def st_sections():
    """The .st split into what each TwinCAT file holds: name -> (declaration, body)."""
    sections = {}
    for m in re.finditer(r'((?:\{attribute [^}]*\}\n)*TYPE (\w+) :.*?END_TYPE\n)', ST_TEXT,
                         re.S):
        sections[m.group(2)] = (m.group(1), None)
    fb = re.search(r'(FUNCTION_BLOCK (\w+)\n.*\nEND_VAR\n)(.*)END_FUNCTION_BLOCK\n', ST_TEXT,
                   re.S)
    sections[fb.group(2)] = (fb.group(1), fb.group(3))
    return sections


class Files(unittest.TestCase):

    def read(self, name):
        with open(os.path.join(TEMPLATES, name), 'rb') as f:
            return f.read()

    def test_twincat_files_are_utf8_with_bom_and_crlf(self):
        for name in TWINCAT:
            with self.subTest(file=name):
                raw = self.read(name)
                self.assertTrue(raw.startswith(BOM))
                self.assertEqual(raw.count(b'\n'), raw.count(b'\r\n'))
                raw.decode('utf-8')

    def test_twincat_files_hold_the_text_of_the_st(self):
        sections = st_sections()
        for name, element in TWINCAT.items():
            with self.subTest(file=name):
                text = self.read(name)[len(BOM):].decode('utf-8').replace('\r\n', '\n')
                obj = ET.fromstring(text).find(element)
                self.assertEqual(obj.get('Name'), name.split('.')[0])
                decl, body = sections[obj.get('Name')]
                self.assertEqual(obj.find('Declaration').text, decl)
                if body is not None:
                    self.assertEqual(obj.find('Implementation/ST').text, body)

    def test_object_ids_are_fresh_guids(self):
        ids = []
        for name in TWINCAT:
            text = self.read(name).decode('utf-8-sig')
            ids += re.findall(r'Id="([^"]*)"', text)
        self.assertEqual(len(ids), len(TWINCAT))
        self.assertEqual(len(set(ids)), len(ids))
        for i in ids:
            self.assertRegex(i, GUID)

    def test_plain_st_is_utf8_without_bom_and_lf(self):
        raw = self.read('FB_Cia402Axis.st')
        self.assertFalse(raw.startswith(BOM))
        self.assertNotIn(b'\r', raw)

    def test_every_type_the_fb_uses_is_shipped(self):
        self.assertEqual(set(st_sections()), {n.split('.')[0] for n in TWINCAT})


class PdoTables(unittest.TestCase):
    """The mapping tables in templates/README.md pass cia402.py pdo without a finding."""

    def tables(self):
        with open(os.path.join(TEMPLATES, 'README.md'), encoding='utf-8') as f:
            text = f.read()
        found = {}
        for m in re.finditer(r'^### (.+?)\n(.*?)(?=^#|\Z)', text, re.S | re.M):
            rows = re.findall(r'^\| (RxPDO|TxPDO) \| 0x([0-9A-F]{4}) \|', m.group(2), re.M)
            modes = re.search(r'--mode ([a-z0-9,]+)', m.group(2))
            if rows and modes:
                found[m.group(1)] = (modes.group(1), rows)
        return found

    def test_each_table_is_clean(self):
        tables = self.tables()
        self.assertEqual(len(tables), 2)
        for title, (modes, rows) in tables.items():
            with self.subTest(table=title):
                rx = [cia402.parse_entry(i) for d, i in rows if d == 'RxPDO']
                tx = [cia402.parse_entry(i) for d, i in rows if d == 'TxPDO']
                result = cia402.check_pdo(rx, tx, [cia402.resolve_mode(m)
                                                   for m in modes.split(',')])
                self.assertEqual(result['findings'], [])

    def test_every_object_the_fb_exchanges_is_in_a_table(self):
        members = {'nStatusword': '6041', 'nModesDisplay': '6061',
                   'nPositionActual': '6064', 'nControlword': '6040',
                   'nModesOfOperation': '6060', 'nTargetPosition': '607A'}
        mapped = {i for _, rows in self.tables().values() for _, i in rows}
        self.assertLessEqual(set(members.values()), mapped)


if __name__ == '__main__':
    unittest.main()
