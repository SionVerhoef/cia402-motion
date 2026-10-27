"""Tests for templates/: FB_Cia402Axis run against a simulated drive, and its files.

    python3 -m unittest discover -s tests -v

The FB's own Structured Text runs in st_subset.py, a deliberately small interpreter, so
what is tested is the template's text and not a Python copy of it. The simulated drive
moves on test_cia402.model_drive, written from the controlword bit rules independently
of cia402.TRANSITIONS, and checks the ordering rules of references/state-machine.md on
every scan: it records a violation whenever the FB breaks one. Every scenario ends with
no violations, and the transitions the drive took are compared with cia402.plan.

None of this is a real drive. It shows that the template keeps the rules against the
profile's state machine; it cannot show what a particular drive does.
"""
import io
import os
import re
import sys
import unittest
import xml.etree.ElementTree as ET

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

# Error codes, written out as the template's header lists them.
ERR = {'not_ready': 0x8101, 'shutdown': 0x8102, 'switch_on': 0x8103, 'enable': 0x8104,
       'mode': 0x8105, 'stop': 0x8106, 'homing_time': 0x8107, 'drive_fault': 0x8110,
       'reset_failed': 0x8111, 'quick_stop': 0x8112, 'left_state': 0x8113,
       'homing': 0x8114, 'statusword': 0x8115, 'no_mode': 0x8120}

# Short timeouts keep the scenarios to a few hundred scans.
FAST = {'tStateTimeout': Time(200), 'tStopTimeout': Time(500), 'tHomingTimeout': Time(1000),
        'tResetPause': Time(100), 'tStandstill': Time(50), 'nResetAttempts': 3,
        'nStandstillWindow': 0}


class SimDrive:
    """A CiA 402 drive for the FB to talk to. step() takes the FB's outputs for one
    cycle; the attributes are what the drive reports back for the next."""

    def __init__(self, state='switch_on_disabled', position=1000, modes=(1, 6, 8, 9, 10),
                 quick_stop_stays=False, settle=1, mode_delay=2, qs_ramp=10,
                 homing_scans=8, home_position=0, homing_phase=0x0400, homing_fails=False,
                 boot_scans=5, fra_scans=3, jitter=0, refuse=()):
        self.state, self.position, self.modes = state, position, modes
        self.quick_stop_stays, self.settle, self.mode_delay = quick_stop_stays, settle, mode_delay
        self.qs_ramp, self.homing_scans, self.home_position = qs_ramp, homing_scans, home_position
        self.homing_phase, self.homing_fails = homing_phase, homing_fails
        self.boot_scans, self.fra_scans, self.jitter = boot_scans, fra_scans, jitter
        self.refuse = refuse  # transitions this drive will not take, by target state
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

    # what the FB reads

    def statusword(self):
        if self.override_sw is not None:
            return self.override_sw
        sw = STATE_BITS[self.state] | VOLTAGE | REMOTE
        if self.state == 'operation_enabled' and self.display == 6:
            sw |= self.homing_phase
        return sw

    # events from outside the FB

    def fault(self, persists=False):
        self.fault_persists = persists
        self._move('fault_reaction_active', None)
        self.timer = 0

    def external_quick_stop(self):
        assert self.state == 'operation_enabled'
        self._move('quick_stop_active', None)
        self.ramp_left = self.qs_ramp

    def drop(self, state):
        self._move(state, None)

    # one cycle

    def violation(self, text):
        self.violations.append(f'scan {self.scan}: {text}')

    def _move(self, to, cw):
        if to != self.state:
            self.transitions.append((self.state, to, cw))
            self.state = to

    def step(self, cw, mode_out, target, velocity, torque, enabled):
        self.scan += 1
        before = self.state
        # Against the position the FB read this cycle, before the drive moves on.
        safe = (target == self.position and velocity == 0 and torque == 0
                and cw & MODE_BITS == 0)
        self._check_words(cw, before)
        if self.last and mode_out != self.last['mode_out']:
            if not self.last['safe']:
                self.violation(f'0x6060 = {mode_out} written while the set-points of the '
                               f'previous cycle were not safe')

        self.recent = (self.recent + [cw])[-self.settle:]
        self.prev_accepted = self.accepted
        if len(self.recent) == self.settle and len(set(self.recent)) == 1:
            self.accepted = cw
        accepted = self.accepted

        # Commanded transitions, then the ones the drive takes by itself.
        new = model_drive(self.state, accepted, self.prev_accepted, self.quick_stop_stays)
        if self.state == 'fault' and new != 'fault' and self.fault_persists:
            new = 'fault'
        if new in self.refuse:
            new = self.state
        if self.state == 'quick_stop_active' and new != 'quick_stop_active' and self.ramp_left:
            self.violation(f'quick stop cut {self.ramp_left} scans before the motor stopped '
                           f'(controlword 0x{accepted:04X})')
        if new != self.state:
            self._entering(new, accepted, target, velocity, torque, enabled)
            self._move(new, accepted)
        self._by_itself()

        # 0x6061 follows 0x6060 after a delay, for the modes the drive has.
        self.mode_queue.append(mode_out)
        if len(self.mode_queue) > self.mode_delay:
            wanted = self.mode_queue.pop(0)
            if wanted in self.modes and wanted != self.display:
                self._display_changes(wanted, target, velocity, torque)
                self.display = wanted

        self._homing(accepted)
        self._motion(target)
        self.last = {'mode_out': mode_out, 'safe': safe}

    def _check_words(self, cw, state):
        if cw & 0x80 and cw & 0x0F:
            self.violation(f'0x{cw:04X}: fault reset with the enable bits')
        if cw & 0x80 and state != 'fault':
            self.violation(f'0x{cw:04X}: bit 7 sent in {state}')
        if state == 'operation_enabled' and not cw & 0x02:
            self.violation(f'0x{cw:04X}: Disable voltage from Operation enabled (T9)')
        if state == 'quick_stop_active' and cw & 0x8F == 0x0F:
            self.violation(f'0x{cw:04X}: Enable operation in Quick stop active (T16)')

    def _entering(self, new, cw, target, velocity, torque, enabled):
        if new != 'operation_enabled':
            return
        if not enabled:
            self.violation('Operation enabled entered while bEnable was FALSE')
        if cw & MODE_BITS:
            self.violation(f'enabled with mode bits set: 0x{cw:04X}')
        self._setpoint_safe(self.display, target, velocity, torque, 'on enable')

    def _display_changes(self, mode, target, velocity, torque):
        if self.state == 'operation_enabled':
            self._setpoint_safe(mode, target, velocity, torque, f'on the switch to {mode}')

    def _setpoint_safe(self, mode, target, velocity, torque, when):
        if mode == 8 and target != self.position:
            self.violation(f'CSP jump {when}: target {target}, actual {self.position}')
        if mode in (3, 9) and velocity:
            self.violation(f'velocity {velocity} {when}')
        if mode in (4, 10) and torque:
            self.violation(f'torque {torque} {when}')

    def _by_itself(self):
        self.timer += 1
        if self.state == 'not_ready_to_switch_on' and self.timer > self.boot_scans:
            self._move('switch_on_disabled', None)
        elif self.state == 'fault_reaction_active' and self.timer > self.fra_scans:
            self._move('fault', None)
        elif self.state == 'quick_stop_active' and self.ramp_left:
            self.position += self.ramp_left  # decelerating
            self.ramp_left -= 1
            if not self.ramp_left and not self.quick_stop_stays:
                self._move('switch_on_disabled', None)
        if self.state not in ('not_ready_to_switch_on', 'fault_reaction_active'):
            self.timer = 0

    def _homing(self, cw):
        if self.state != 'operation_enabled' or self.display != 6:
            self.homing_left = None
            return
        start = cw & 0x10 and not self.prev_accepted & 0x10
        if start:
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
        if self.state == 'operation_enabled' and self.display == 8:
            self.position = target
        elif self.jitter and not self.ramp_left and self.homing_left is None:
            self.position += self.jitter * self.jitter_sign
            self.jitter_sign = -self.jitter_sign


class Rig:
    """The FB, its drive and the inputs the test sets; scan() runs one cycle."""

    def __init__(self, drive, **config):
        self.drive = drive
        self.fb = PROGRAM.instance('FB_Cia402Axis')
        self.io = Struct(PROGRAM, 'ST_Cia402Drive')
        self.config = Struct(PROGRAM, 'ST_Cia402Config')
        for name, value in dict(FAST, **config).items():
            self.config[name] = value
        self.enable, self.mode, self.reset = False, 0, False
        self.caller = None  # writes set-points while bValid, as an application would
        self.now = 0
        self.words = []     # every controlword the FB wrote
        self.out = None

    def scan(self):
        d = self.drive
        self.io['nStatusword'] = d.statusword()
        self.io['nModesDisplay'] = d.display
        self.io['nPositionActual'] = d.position
        self.out = self.fb.scan(self.now, bEnable=self.enable, nMode=self.mode,
                                bReset=self.reset, stConfig=self.config, stDrive=self.io)
        if self.out['bValid'] and self.caller:
            self.caller(self)
        cw = self.io['nControlword']
        self.words.append(cw)
        d.step(cw, self.io['nModesOfOperation'], self.io['nTargetPosition'],
               self.io['nTargetVelocity'], self.io['nTargetTorque'], self.enable)
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
                             f'outputs {self.out}')

    def pulse_reset(self):
        self.reset = True
        self.scan()
        self.reset = False

    def valid(self):
        return self.until(lambda r: r.out['bValid'], what='bValid')

    def at_rest(self):
        return self.until(lambda r: r.drive.state == 'switch_on_disabled'
                          and not r.out['bBusy'], what='rest in Switch on disabled')

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


class TemplateCase(unittest.TestCase):

    def tearDown(self):
        rig = getattr(self, 'rig', None)
        if rig is not None:
            self.assertEqual(rig.drive.violations, [])

    def make(self, **drive):
        config = drive.pop('config', {})
        self.rig = Rig(SimDrive(**drive), **config)
        return self.rig

    def running(self, mode=8, **drive):
        rig = self.make(**drive)
        rig.enable, rig.mode = True, mode
        rig.valid()
        return rig


class Decode(TemplateCase):

    def test_every_statusword_pattern_against_the_decoder(self):
        # The states depend on bits 0-6 only; three settings of the high bits on top.
        fb = PROGRAM.instance('FB_Cia402Axis')
        io, config = Struct(PROGRAM, 'ST_Cia402Drive'), Struct(PROGRAM, 'ST_Cia402Config')
        for high in (0x0000, 0x0200, 0xFF80):
            for low in range(0x80):
                sw = high | low
                io['nStatusword'] = sw
                out = fb.scan(0, bEnable=False, nMode=0, bReset=False, stConfig=config,
                              stDrive=io)
                r = cia402.decode_statusword(sw)
                key = r['state'] or (r['treat_as'] if r['treat_as'] in
                                     ('fault', 'fault_reaction_active') else None)
                with self.subTest(sw=f'0x{sw:04X}'):
                    self.assertEqual(out['eDriveState'].name, ENUM_OF.get(key, 'Unknown'))


class Enabling(TemplateCase):

    def test_from_each_state_as_the_planner_says(self):
        for start in ('switch_on_disabled', 'ready_to_switch_on', 'switched_on',
                      'not_ready_to_switch_on', 'quick_stop_active'):
            with self.subTest(start=start):
                rig = self.make(state=start)
                rig.enable, rig.mode = True, 8
                rig.valid()
                self.assertEqual(rig.drive.transitions,
                                 plan_transitions(start, 'operation_enabled', 'csp'))
                self.assertEqual(rig.drive.violations, [])

    def test_from_fault_after_a_reset(self):
        rig = self.make(state='fault')
        rig.enable, rig.mode = True, 8
        self.assertTrue(rig.error(ERR['drive_fault']))
        self.assertEqual(rig.words[-1], 0x0000)
        mark = len(rig.words)
        rig.pulse_reset()
        rig.valid()
        self.assertEqual(rig.drive.transitions,
                         plan_transitions('fault', 'operation_enabled', 'csp'))
        # Bit 7 low before the edge, released after it, then the way up.
        self.assertEqual(rig.distinct_words(mark), [0x0000, 0x0080, 0x0000, 0x0006,
                                                    0x0007, 0x000F])

    def test_an_enabled_drive_is_taken_down_to_switched_on_first(self):
        rig = self.make(state='operation_enabled', modes=(8,))
        rig.drive.display = 8
        rig.enable, rig.mode = True, 8
        rig.valid()
        self.assertEqual(rig.drive.transitions,
                         plan_transitions('operation_enabled', 'switched_on')
                         + plan_transitions('switched_on', 'operation_enabled', 'csp'))

    def test_csp_target_follows_actual_until_valid(self):
        rig = self.make(position=-123456)
        rig.enable, rig.mode = True, 8
        rig.valid()
        self.assertEqual(rig.io['nTargetPosition'], -123456)
        self.assertEqual(rig.io['nModesOfOperation'], 8)

    def test_set_points_are_the_callers_once_valid(self):
        rig = self.running(position=500)
        rig.caller = lambda r: r.io.__setitem__('nTargetPosition',
                                                r.io['nTargetPosition'] + 7)
        rig.run(10)
        self.assertEqual(rig.drive.position, 570)
        self.assertTrue(rig.out['bValid'])

    def test_mode_bits_pass_only_while_valid(self):
        rig = self.make(state='switch_on_disabled')
        rig.io['nModeBits'] = 0xFFFF
        rig.enable, rig.mode = True, 1
        rig.valid()
        self.assertTrue(all(w & MODE_BITS == 0 for w in rig.words[:-1]))
        rig.scan()
        self.assertEqual(rig.words[-1], 0x000F | MODE_BITS)

    def test_mode_zero_is_an_error(self):
        rig = self.make()
        rig.enable = True
        self.assertTrue(rig.error(ERR['no_mode']))


class Disabling(TemplateCase):

    def test_way_down_from_operation_enabled_as_the_planner_says(self):
        rig = self.running()
        mark = len(rig.drive.transitions)
        rig.enable = False
        rig.at_rest()
        self.assertEqual(rig.drive.transitions[mark:],
                         plan_transitions('operation_enabled', 'switch_on_disabled'))

    def test_way_down_from_each_other_state(self):
        for start in ('ready_to_switch_on', 'switched_on'):
            with self.subTest(start=start):
                rig = self.make(state=start)
                rig.at_rest()
                self.assertEqual(rig.drive.transitions,
                                 plan_transitions(start, 'switch_on_disabled'))

    def test_disabled_at_rest_is_neither_busy_nor_valid(self):
        rig = self.make()
        rig.run(20)
        self.assertEqual(rig.out['bBusy'], False)
        self.assertEqual(rig.out['bValid'], False)
        self.assertEqual(set(rig.words), {0x0000})

    def test_stop_that_does_not_end_is_an_error(self):
        rig = self.running()
        rig.drive.refuse = ('switched_on',)
        rig.enable = False
        self.assertTrue(rig.error(ERR['stop']))
        self.assertEqual(rig.words[-1], 0x0007)  # still asking for the stop


class QuickStop(TemplateCase):

    def test_external_quick_stop_is_left_to_finish(self):
        rig = self.running()
        rig.drive.external_quick_stop()
        mark = len(rig.words)
        self.assertTrue(rig.error(ERR['quick_stop']))
        rig.until(lambda r: r.drive.state == 'switch_on_disabled', what='end of the stop')
        held = rig.words[mark:mark + rig.drive.qs_ramp]
        self.assertEqual(set(held), {0x0002})
        rig.run(3)
        self.assertEqual(rig.words[-1], 0x0000)
        rig.pulse_reset()
        rig.valid()

    def test_quick_stop_that_stays_is_left_at_standstill(self):
        rig = self.running(quick_stop_stays=True)
        rig.drive.external_quick_stop()
        mark = len(rig.words)
        rig.until(lambda r: r.drive.state == 'switch_on_disabled', what='T12')
        cut = rig.words.index(0x0000, mark) - mark
        # The ramp, then tStandstill of no motion; never the timer of a fixed delay.
        self.assertGreaterEqual(cut, rig.drive.qs_ramp + 50 // CYCLE)
        self.assertEqual(rig.drive.transitions[-1],
                         ('quick_stop_active', 'switch_on_disabled', 0x0000))

    def test_jitter_without_a_band_holds_the_quick_stop(self):
        rig = self.running(quick_stop_stays=True, jitter=1)
        rig.drive.external_quick_stop()
        rig.run(200)
        self.assertEqual(rig.drive.state, 'quick_stop_active')
        self.assertEqual(rig.words[-1], 0x0002)

    def test_a_band_over_the_jitter_finds_standstill(self):
        rig = self.running(quick_stop_stays=True, jitter=1, config={'nStandstillWindow': 2})
        rig.drive.external_quick_stop()
        rig.until(lambda r: r.drive.state == 'switch_on_disabled', what='T12')


class FaultReset(TemplateCase):

    def test_fault_while_running_then_reset(self):
        rig = self.running()
        rig.drive.fault()
        self.assertTrue(rig.error(ERR['drive_fault']))
        rig.run(10)
        self.assertEqual(rig.words[-1], 0x0000)
        mark = len(rig.words)
        rig.pulse_reset()
        rig.valid()
        self.assertEqual(rig.distinct_words(mark), [0x0000, 0x0080, 0x0000, 0x0006,
                                                    0x0007, 0x000F])

    def test_failed_resets_release_bit_7_every_time(self):
        rig = self.running()
        rig.drive.fault(persists=True)
        rig.error(ERR['drive_fault'])
        rig.run(10)
        mark = len(rig.words)
        rig.pulse_reset()
        self.assertTrue(rig.error(ERR['reset_failed']))
        words = rig.words[mark:]
        edges = [i for i in range(1, len(words)) if words[i] & 0x80 and not words[i - 1] & 0x80]
        self.assertEqual(len(edges), 3)  # nResetAttempts
        for i in edges:
            high = 0
            while words[i + high] & 0x80:
                high += 1
            # tStateTimeout, then released. A step's word goes out on the scan it is
            # entered and its timer re-arms on the next, so allow two cycles over.
            self.assertLessEqual(high * CYCLE, 200 + 2 * CYCLE)
            self.assertEqual(words[i + high], 0x0000)
        self.assertEqual(rig.words[-1], 0x0000)
        rig.run(50)
        self.assertEqual(rig.words[-1], 0x0000)

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
        rig3 = self.make()
        rig3.enable, rig3.mode = True, 8
        rig3.valid()
        rig3.drive.refuse = ('switched_on',)
        rig3.enable = False
        rig3.error(ERR['stop'])
        rig3.pulse_reset()
        rig3.run(20)
        self.assertEqual(rig3.drive.state, 'operation_enabled')
        self.assertFalse(any(w & 0x80 for w in rig.words + rig2.words + rig3.words))
        self.assertEqual(rig.drive.violations + rig2.drive.violations, [])


class ModeSwitch(TemplateCase):

    def test_switch_while_enabled_is_confirmed_on_6061(self):
        rig = self.running(position=40)
        rig.caller = lambda r: r.io.__setitem__('nTargetPosition',
                                                r.io['nTargetPosition'] + 3)
        rig.run(5)
        rig.caller = lambda r: r.io.__setitem__('nTargetVelocity', 250)
        rig.mode = 9
        rig.scan()
        self.assertFalse(rig.out['bValid'])
        rig.valid()
        self.assertEqual(rig.drive.display, 9)
        self.assertEqual(rig.io['nModesOfOperation'], 9)
        self.assertEqual(rig.drive.state, 'operation_enabled')

    def test_unsupported_mode_times_out_and_goes_down(self):
        rig = self.running()
        mark = len(rig.drive.transitions)
        rig.mode = 7
        self.assertTrue(rig.error(ERR['mode']))
        rig.until(lambda r: r.drive.state == 'switch_on_disabled', what='way down')
        self.assertEqual(rig.drive.transitions[mark:],
                         plan_transitions('operation_enabled', 'switch_on_disabled'))


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
        # A drive slow to act on bit 4 (settle) still shows the old 'completed' then.
        rig = self.make(homing_phase=0x1400, homing_scans=8, settle=3)
        rig.enable, rig.mode = True, 6
        rig.until(lambda r: r.words[-1] == 0x001F, what='bit 4')
        started = len(rig.words)
        rig.valid()
        self.assertGreater(len(rig.words) - started, 8)

    def test_homing_error_takes_the_drive_down(self):
        rig = self.make(homing_fails=True)
        rig.enable, rig.mode = True, 6
        self.assertTrue(rig.error(ERR['homing']))
        rig.until(lambda r: r.drive.state == 'switch_on_disabled', what='way down')
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


class Errors(TemplateCase):

    def test_transition_the_drive_refuses_times_out(self):
        rig = self.make(refuse=('switched_on',))
        rig.enable, rig.mode = True, 8
        n = rig.until(lambda r: r.out['bError'], what='timeout')
        self.assertEqual(rig.out['nErrorID'], ERR['switch_on'])
        self.assertGreaterEqual(n * CYCLE, 200)
        rig.at_rest()  # T7 on the way down

    def test_drive_that_drops_out_is_not_enabled_again_without_reset(self):
        rig = self.running()
        rig.drive.drop('switch_on_disabled')
        self.assertTrue(rig.error(ERR['left_state']))
        rig.run(50)
        self.assertEqual(rig.drive.state, 'switch_on_disabled')
        self.assertEqual(rig.words[-1], 0x0000)
        rig.pulse_reset()
        rig.valid()

    def test_drive_that_never_boots(self):
        rig = self.make(state='not_ready_to_switch_on', boot_scans=10000)
        rig.enable, rig.mode = True, 8
        self.assertTrue(rig.error(ERR['not_ready']))

    def test_statusword_that_decodes_to_nothing(self):
        rig = self.running()
        rig.drive.override_sw = 0x0005
        self.assertTrue(rig.error(ERR['statusword']))
        self.assertEqual(rig.words[-1], 0x000F)  # held until the word decodes again
        rig.drive.override_sw = None
        rig.scan()
        self.assertEqual(rig.words[-1], 0x0007)  # then the way down, T5

    def test_defaults_of_the_config(self):
        rig = Rig(SimDrive(refuse=('switched_on',)))
        for name in FAST:
            rig.config[name] = Struct(PROGRAM, 'ST_Cia402Config')[name]
        rig.enable, rig.mode = True, 8
        n = rig.until(lambda r: r.out['bError'], limit=400, what='timeout')
        self.assertGreaterEqual(n * CYCLE, 2000)  # T#2S, plus the scans to get there
        self.assertLess(n * CYCLE, 2100)
        self.rig = rig


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
                     'FOR x := 1 TO 3 DO END_FOR'):
            with self.subTest(text=text), self.assertRaises(StError):
                self.run_body(text)

    def test_precedence(self):
        fb = self.run_body('b := 1 + 2 * 3 = 7 AND NOT FALSE;')
        self.assertTrue(fb['b'])


# One edit per rule, each breaking it in the template's text. A rule whose break no
# scenario notices has lost its test.
BROKEN_RULES = {
    'quick stop cut with 0x0000': (
        "stDrive.nControlword := 16#0002;   // let it finish",
        "stDrive.nControlword := 16#0000;   // let it finish"),
    'quick stop left on a timer': (
        "IF fbStandstill.Q THEN\n                    stDrive.nControlword := 16#0000;",
        "IF fbStandstill.Q OR fbStepTimer.Q THEN\n                    stDrive.nControlword := 16#0000;"),
    'T9 from Operation enabled': (
        "stDrive.nControlword := 16#0007;   // T5, stops as 0x605C",
        "stDrive.nControlword := 16#0000;   // T5, stops as 0x605C"),
    'bit 7 never released': (
        "IF (eDriveState <> E_Cia402State.Fault) OR fbStepTimer.Q THEN",
        "IF eDriveState <> E_Cia402State.Fault THEN"),
    'bit 7 with the enable bits': (
        "            stDrive.nControlword := 16#0080;\n",
        "            stDrive.nControlword := 16#008F;\n"),
    'reset outside Fault': (
        "            IF eDriveState = E_Cia402State.Fault THEN\n                nErrorID    := 0;",
        "            IF TRUE THEN\n                nErrorID    := 0;"),
    'stale homing result taken': (
        "        ELSIF bHomingRunSeen\n              AND",
        "        ELSIF TRUE\n              AND"),
    '0x6060 in the same scan as the set-points': (
        "        IF bHeldLastScan THEN\n            stDrive.nModesOfOperation := nMode;",
        "        IF TRUE THEN\n            stDrive.nModesOfOperation := nMode;"),
    'target not held at actual': (
        "    stDrive.nTargetPosition := stDrive.nPositionActual;\n",
        ""),
    'one 0x6F mask for every state': (
        "IF (stDrive.nStatusword AND 16#004F) = 16#0000 THEN",
        "IF (stDrive.nStatusword AND 16#006F) = 16#0000 THEN"),
    'mode not confirmed on 0x6061': (
        "              AND (stDrive.nModesDisplay = nMode)\n        THEN\n            IF eDriveState",
        "        THEN\n            IF eDriveState"),
    'drop out re-enabled without reset': (
        "            nErrorID := cErrLeftState;\n            eStep    := E_Cia402Step.Error;\n        ELSIF (nMode <> stDrive.nModesOfOperation)\n              OR (nMode <> stDrive.nModesDisplay)\n        THEN\n            eStep := E_Cia402Step.SetMode;\n        END_IF\n\n    E_Cia402Step.ResetLow:",
        "            eStep    := E_Cia402Step.Disabled;\n        ELSIF (nMode <> stDrive.nModesOfOperation)\n              OR (nMode <> stDrive.nModesDisplay)\n        THEN\n            eStep := E_Cia402Step.SetMode;\n        END_IF\n\n    E_Cia402Step.ResetLow:"),
    'mode bits before valid': (
        "        stDrive.nControlword := 16#0007;   // T3",
        "        stDrive.nControlword := 16#0007 OR stDrive.nModeBits;   // T3"),
}


class BrokenRules(unittest.TestCase):
    """Every rule broken on purpose makes a scenario fail."""

    def test_each_broken_rule_is_caught(self):
        global PROGRAM
        loader = unittest.TestLoader()
        scenarios = (Decode, Enabling, Disabling, QuickStop, FaultReset, ModeSwitch, Homing,
                     Errors)
        try:
            for rule, (old, new) in BROKEN_RULES.items():
                with self.subTest(rule=rule):
                    self.assertEqual(ST_TEXT.count(old), 1, 'the edit no longer applies')
                    PROGRAM = Program(ST_TEXT.replace(old, new))
                    suite = unittest.TestSuite(loader.loadTestsFromTestCase(c)
                                               for c in scenarios)
                    runner = unittest.TextTestRunner(stream=io.StringIO(), failfast=True)
                    result = runner.run(suite)
                    self.assertTrue(result.failures or result.errors,
                                    'no scenario failed')
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
