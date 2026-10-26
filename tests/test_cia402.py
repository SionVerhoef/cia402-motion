"""Tests for scripts/cia402.py. Plain unittest, standard library only.

    python3 -m unittest discover -s tests -v

The planner is checked against a model drive written from the controlword bit rules,
independently of cia402.TRANSITIONS, so a wrong row in that table cannot also make
its own test pass. Expected meanings are written out literally here rather than read
back from the script's tables. The cross-check against python-canopen is in
test_canopen_oracle.py.
"""
import contextlib
import io
import json
import os
import re
import subprocess
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.join(os.path.dirname(HERE), 'scripts')
sys.path.insert(0, SCRIPTS)

import cia402  # noqa: E402

COMMANDABLE = [k for k in cia402.STATES if k not in cia402.UNCOMMANDABLE]


def model_drive(state, cw, prev_cw, quick_stop_stays=False):
    """The state a drive moves to when it sees controlword cw after prev_cw."""
    if state in ('not_ready_to_switch_on', 'fault_reaction_active'):
        return state  # these do not react to the controlword
    if state == 'fault':
        return 'switch_on_disabled' if cw & 0x80 and not prev_cw & 0x80 else 'fault'
    if cw & 0x80:
        return state  # every command but fault reset needs bit 7 = 0
    voltage, quick_stop_off = cw & 0x02, cw & 0x04
    switch_on, enable = cw & 0x01, cw & 0x08
    if state == 'switch_on_disabled':
        return 'ready_to_switch_on' if voltage and quick_stop_off and not switch_on else state
    if not voltage:
        return 'switch_on_disabled'
    if state == 'quick_stop_active':
        if quick_stop_stays and quick_stop_off and switch_on and enable:
            return 'operation_enabled'
        return state
    if not quick_stop_off:
        return 'quick_stop_active' if state == 'operation_enabled' else 'switch_on_disabled'
    if not switch_on:
        return 'ready_to_switch_on'
    if state == 'ready_to_switch_on':
        return 'switched_on'
    if state == 'switched_on':
        return 'operation_enabled' if enable else state
    return 'operation_enabled' if enable else 'switched_on'


def model_auto(state, quick_stop_stays=False):
    """The state a drive moves to by itself, given time."""
    if state == 'not_ready_to_switch_on':
        return 'switch_on_disabled'
    if state == 'fault_reaction_active':
        return 'fault'
    if state == 'quick_stop_active' and not quick_stop_stays:
        return 'switch_on_disabled'
    return state


def replay(test, result, prev_cw, quick_stop_stays):
    """Run a plan's steps through the model drive; return the final state."""
    state = result['from']
    for step in result['steps']:
        if step['kind'] == 'prepare':
            continue
        before = state
        if step['kind'] == 'wait':
            state = model_auto(state, quick_stop_stays)
        else:
            cw = step['controlword']
            # Only the state-machine bits and fault reset: a stray bit 4 would start a
            # move or a homing run on enable, bit 8 would halt.
            test.assertEqual(cw & ~0x008F, 0, step)
            state = model_drive(state, cw, prev_cw, quick_stop_stays)
            prev_cw = cw
        test.assertEqual(state, step['expect'],
                         f'{result["from"]} -> {result["to"]}: step {step} left the model '
                         f'in {state}')
        if result['to'] != 'operation_enabled':
            test.assertNotEqual(state, 'operation_enabled',
                                'a plan to another state passed through Operation enabled')
        if step['transition']:
            t = cia402.TRANSITION[step['transition']]
            test.assertEqual((t['from'], t['to']), (before, state))
    return state


def run_main(args):
    """cia402.main() in-process: (exit code, stdout)."""
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = cia402.main(args)
    return code, out.getvalue()


class StatuswordStates(unittest.TestCase):

    def test_each_state_from_its_own_value(self):
        for key, s in cia402.STATES.items():
            with self.subTest(state=key):
                self.assertEqual(cia402.decode_statusword(s['value'])['state'], key)

    def test_masks_never_overlap(self):
        for sw in range(0x10000):
            hits = [k for k, s in cia402.STATES.items() if sw & s['mask'] == s['value']]
            self.assertLessEqual(len(hits), 1, f'0x{sw:04X} matches {hits}')

    def test_bit5_set_in_fault_and_switch_on_disabled(self):
        # The bug in decoders that mask every state with 0x6F: bit 5 is a don't-care
        # in these states, so 0x0028 and 0x0060 then match nothing.
        self.assertNotEqual(0x0028 & 0x6F, 0x08)
        self.assertEqual(cia402.decode_statusword(0x0028)['state'], 'fault')
        self.assertEqual(cia402.decode_statusword(0x0060)['state'], 'switch_on_disabled')

    def test_statuswords_seen_in_the_field(self):
        # Values from the public issue logs listed in ATTRIBUTIONS.md; the decodes are
        # our own arithmetic.
        cases = {648: 'fault', 4744: 'fault', 720: 'switch_on_disabled',
                 4785: 'ready_to_switch_on', 691: 'switched_on', 4791: 'operation_enabled'}
        for sw, state in cases.items():
            with self.subTest(sw=sw):
                self.assertEqual(cia402.decode_statusword(sw)['state'], state)

    def test_non_standard_0x0068_is_treated_as_fault(self):
        r = cia402.decode_statusword(0x0068)
        self.assertIsNone(r['state'])
        self.assertTrue(r['nonstandard'])
        self.assertEqual(r['treat_as'], 'fault')
        self.assertIn('0x603F', r['notes'][0])
        self.assertEqual(r['next']['controlword'], 0x0000)
        self.assertEqual(r['next']['command'], 'hold bit 7 low')

    def test_how_non_standard_values_are_read(self):
        cases = {0x41: 'switch_on_disabled', 0x43: 'switch_on_disabled',
                 0x01: 'ready_to_switch_on', 0x03: 'switched_on', 0x48: 'fault',
                 0x68: 'fault', 0x09: 'fault', 0x4F: 'fault_reaction_active',
                 0x02: None, 0x04: None, 0x05: None, 0x06: None}
        for sw, treat_as in cases.items():
            with self.subTest(sw=hex(sw)):
                r = cia402.decode_statusword(sw)
                self.assertIsNone(r['state'])
                self.assertEqual(r['treat_as'], treat_as)
        self.assertIn('bits 2-0 are 100', cia402.decode_statusword(0x04)['notes'][0])

    def test_every_value_decodes_and_fault_comes_first(self):
        for sw in range(0x10000):
            r = cia402.decode_statusword(sw)
            self.assertEqual(r['nonstandard'], r['state'] is None)
            if r['nonstandard'] and sw & 0x08:
                self.assertIn(r['treat_as'], ('fault', 'fault_reaction_active'), hex(sw))

    def test_only_broken_low_bits_have_no_reading(self):
        for sw in range(0x80):
            r = cia402.decode_statusword(sw)
            if r['nonstandard'] and r['treat_as'] is None:
                self.assertFalse(sw & 0x48, hex(sw))
                self.assertIn(sw & 0x07, (0x02, 0x04, 0x05, 0x06), hex(sw))

    def test_next_step_toward_operation_enabled(self):
        expect = {'switch_on_disabled': ('write', 0x0006), 'ready_to_switch_on': ('write', 0x0007),
                  'switched_on': ('write', 0x000F), 'fault': ('write', 0x0000),
                  'quick_stop_active': ('wait', None),
                  'not_ready_to_switch_on': ('wait', None),
                  'fault_reaction_active': ('wait', None)}
        for key, (kind, cw) in expect.items():
            with self.subTest(state=key):
                nxt = cia402.decode_statusword(cia402.STATES[key]['value'])['next']
                self.assertEqual((nxt['kind'], nxt['controlword']), (kind, cw))
        self.assertIsNone(cia402.decode_statusword(0x0027)['next'])

    def test_notes(self):
        cases = [
            (0x0040, None, 'Voltage enabled (bit 4) is 0'),
            (0x0040, None, 'Remote (bit 9) is 0'),
            (0x02B7, None, 'Warning (bit 7)'),
            (0x0A37, None, 'Internal limit active (bit 11)'),
            (0x4137, None, 'Manufacturer-specific bits 8 and 14 set'),
            (0x1237, None, 'Mode-specific bit 12 set'),
            (0x2237, 'csp', 'Following error (bit 13)'),
            (0x020F, None, 'Read 0x603F'),
        ]
        for sw, mode, text in cases:
            with self.subTest(sw=hex(sw), text=text):
                notes = ' '.join(cia402.decode_statusword(sw, cia402.resolve_mode(mode))['notes'])
                self.assertIn(text, notes)
        quiet = ' '.join(cia402.decode_statusword(0x0250)['notes'])
        self.assertNotIn('bit 4', quiet)
        self.assertNotIn('bit 9', quiet)
        self.assertEqual(' '.join(cia402.decode_statusword(0x0218)['notes']).count('0x603F'), 1)


class ModeSpecificBits(unittest.TestCase):

    def meaning(self, result, bit):
        return result['bits'][bit]['meaning']

    def test_statusword_meanings(self):
        cases = [
            ('pp', 10, 'target reached'), ('pp', 12, 'set-point acknowledge'),
            ('pp', 13, 'following error'), ('pv', 12, 'speed is zero'),
            ('pv', 13, 'max slippage error'), ('pt', 12, 'unused in this mode'),
            ('hm', 10, 'target reached'), ('hm', 12, 'homing attained'),
            ('hm', 13, 'homing error'), ('ip', 12, 'interpolation active'),
            ('csp', 10, 'unused in this mode'), ('csp', 12, 'drive follows the command value'),
            ('csp', 13, 'following error'), ('csv', 13, 'unused in this mode'),
            ('cst', 12, 'drive follows the command value'),
        ]
        for mode, bit, meaning in cases:
            with self.subTest(mode=mode, bit=bit):
                r = cia402.decode_statusword(0x3637, cia402.resolve_mode(mode))
                self.assertEqual(self.meaning(r, bit), meaning)
        self.assertEqual(self.meaning(cia402.decode_statusword(0x1637), 12), 'mode-specific')

    def test_controlword_meanings(self):
        cases = [
            ('pp', 4, 'new set-point (rising edge)'), ('pp', 5, 'change set immediately'),
            ('pp', 6, 'relative target (0 = absolute)'), ('pp', 9, 'change on set-point'),
            ('hm', 4, 'homing operation start (rising edge; 1 -> 0 interrupts)'),
            ('hm', 5, 'reserved in this mode'), ('ip', 4, 'enable interpolation'),
            ('csp', 4, 'reserved in this mode'),
        ]
        for mode, bit, meaning in cases:
            with self.subTest(mode=mode, bit=bit):
                r = cia402.decode_controlword(0x027F, cia402.resolve_mode(mode))
                self.assertEqual(self.meaning(r, bit), meaning)

    def test_homing_phases(self):
        hm = cia402.resolve_mode('hm')
        cases = {0x0000: 'in progress', 0x0400: 'interrupted, or not started',
                 0x1000: 'attained, target not reached yet', 0x1400: 'completed',
                 0x2000: 'error, motor still moving', 0x2400: 'error, at standstill'}
        for bits, phase in cases.items():
            with self.subTest(bits=hex(bits)):
                r = cia402.decode_statusword(0x0027 | bits, hm)
                self.assertEqual(r['homing']['phase'], phase)
        for bits in (0x3000, 0x3400):
            r = cia402.decode_statusword(0x0027 | bits, hm)
            self.assertTrue(r['homing']['phase'].startswith('reserved'))

    def test_no_homing_phase_outside_operation_enabled(self):
        r = cia402.decode_statusword(0x0250, cia402.resolve_mode('hm'))
        self.assertIsNone(r['homing']['phase'])
        self.assertIn('Homing runs only in Operation enabled', ' '.join(r['notes']))

    def test_mode_by_code_and_vendor_mode(self):
        self.assertEqual(cia402.resolve_mode('8')[0], 'csp')
        self.assertEqual(cia402.resolve_mode('0xF8')[1], -8)
        self.assertEqual(cia402.resolve_mode('0')[1], 0)
        key, code, _ = cia402.resolve_mode('-3')
        self.assertIsNone(key)
        self.assertEqual(code, -3)
        r = cia402.decode_statusword(0x1637, cia402.resolve_mode('-3'))
        self.assertIn('not decoded', self.meaning(r, 12))
        self.assertEqual(cia402.resolve_mode('11')[0], 'cstca')
        for text in ('5', '12', 'xyz', '300'):
            with self.subTest(text=text):
                with self.assertRaises(ValueError):
                    cia402.resolve_mode(text)

    def test_reserved_mode_bit_in_csp(self):
        r = cia402.decode_controlword(0x001F, cia402.resolve_mode('csp'))
        self.assertTrue(any('should be 0' in n for n in r['notes']))


class Controlword(unittest.TestCase):

    def test_commands(self):
        cases = {0x0006: ('Shutdown', [2, 6, 8]),
                 0x0007: ('Switch on / Disable operation', [3, 5]),
                 0x000F: ('Enable operation', [4, 16]),
                 0x0000: ('Disable voltage', [7, 9, 10, 12]),
                 0x0002: ('Quick stop', [7, 10, 11]), 0x0080: ('Fault reset', [15]),
                 0x000E: ('Shutdown', [2, 6, 8]), 0x0004: ('Disable voltage', [7, 9, 10, 12]),
                 0x000A: ('Quick stop', [7, 10, 11])}
        for cw, expected in cases.items():
            with self.subTest(cw=hex(cw)):
                self.assertEqual(cia402.controlword_command(cw), expected)

    def test_every_transition_controlword_selects_it(self):
        for t in cia402.TRANSITIONS:
            if t['controlword'] is not None:
                with self.subTest(t=t['id']):
                    self.assertIn(t['id'], cia402.controlword_command(t['controlword'])[1])

    def test_every_value_decodes(self):
        for cw in range(0x10000):
            cia402.decode_controlword(cw)

    def test_notes(self):
        cases = [(0x008F, None, 'Release it'), (0x008F, None, 'Bits 0-3 are set as well'),
                 (0x010F, None, 'Halt (bit 8)'), (0x040F, None, 'Bit 10 is reserved'),
                 (0x080F, None, 'Manufacturer-specific bit 11 set'),
                 (0x001F, None, 'Mode-specific bit 4 set'),
                 (0x001F, 'pp', 'wait for statusword bit 12'),
                 (0x000F, None, 'T3, then T4')]
        for cw, mode, text in cases:
            with self.subTest(cw=hex(cw), text=text):
                notes = cia402.decode_controlword(cw, cia402.resolve_mode(mode))['notes']
                self.assertIn(text, ' '.join(notes))


class Planner(unittest.TestCase):

    def plans(self):
        for start in cia402.STATES:
            for target in COMMANDABLE:
                for stays in (False, True):
                    for mode in (None, 'csp', 'pp', 'hm'):
                        yield start, target, stays, mode

    def test_every_plan_reaches_its_target_on_the_model_drive(self):
        for start, target, stays, mode in self.plans():
            for prev_cw in (0x0000, 0x0080, 0x000F):
                with self.subTest(start=start, target=target, stays=stays, mode=mode,
                                  prev=hex(prev_cw)):
                    try:
                        r = cia402.plan(start, target, cia402.resolve_mode(mode), stays)
                    except ValueError:
                        # Only Quick stop active is refused, and only from where getting
                        # there would mean enabling the motor first.
                        self.assertEqual(target, 'quick_stop_active')
                        self.assertNotIn(start, ('operation_enabled', 'quick_stop_active'))
                        continue
                    self.assertEqual(replay(self, r, prev_cw, stays), target)

    def test_bit7_is_set_only_by_the_reset(self):
        for start in cia402.STATES:
            for target in [t for t in COMMANDABLE if t != 'quick_stop_active']:
                writes = [s for s in cia402.plan(start, target)['steps']
                          if s['kind'] == 'write']
                for i, s in enumerate(writes):
                    if s['controlword'] & 0x80:
                        self.assertEqual(s['transition'], 15)
                        self.assertGreater(i, 0)
                        self.assertFalse(writes[i - 1]['controlword'] & 0x80)
                        self.assertFalse(writes[i + 1]['controlword'] & 0x80)

    def test_fault_to_operation_enabled(self):
        steps = cia402.plan('fault')['steps']
        self.assertEqual([s['controlword'] for s in steps],
                         [0x0000, 0x0080, 0x0000, 0x0006, 0x0007, 0x000F])
        self.assertEqual([s['transition'] for s in steps], [None, 15, None, 2, 3, 4])
        self.assertIn('0x607A', steps[-1]['note'])  # set-point caution without --mode

    def test_disable_avoids_coasting(self):
        r = cia402.plan('operation_enabled', 'switch_on_disabled')
        self.assertEqual([s['transition'] for s in r['steps']], [5, 10])

    def test_quick_stop_finishes_before_anything_else(self):
        r = cia402.plan('quick_stop_active')
        self.assertEqual([(s['kind'], s['transition']) for s in r['steps']],
                         [('wait', 12), ('write', 2), ('write', 3), ('write', 4)])
        self.assertTrue(any('--quick-stop-stays' in n for n in r['notes']))
        r = cia402.plan('quick_stop_active', quick_stop_stays=True)
        self.assertEqual([(s['kind'], s['transition']) for s in r['steps']],
                         [('prepare', None), ('write', 16)])
        self.assertIn('standstill', r['steps'][0]['note'])

    def test_quick_stop_to_switched_on_does_not_re_enable(self):
        r = cia402.plan('quick_stop_active', 'switched_on', quick_stop_stays=True)
        self.assertEqual([s['transition'] for s in r['steps']], [None, 12, 2, 3])

    def test_quick_stop_target_only_from_operation_enabled(self):
        self.assertEqual([s['transition'] for s in
                          cia402.plan('operation_enabled', 'quick_stop_active')['steps']], [11])
        with self.assertRaises(ValueError):
            cia402.plan('switch_on_disabled', 'quick_stop_active')

    def test_set_point_comes_before_the_mode_switch(self):
        r = cia402.plan('switch_on_disabled', mode=cia402.resolve_mode('csp'))
        kinds = [s['kind'] for s in r['steps']]
        self.assertEqual(kinds, ['write', 'write', 'prepare', 'prepare', 'write'])
        self.assertIn('0x607A', r['steps'][2]['note'])
        self.assertIn('0x6064', r['steps'][2]['note'])
        self.assertIn('0x6061 reads 8', r['steps'][3]['note'])
        self.assertEqual(r['steps'][4]['transition'], 4)

    def test_mode_switch_while_enabled(self):
        # The drive follows the new mode's set-point as soon as 0x6061 changes, so the
        # set-point must be fixed first.
        r = cia402.plan('operation_enabled', mode=cia402.resolve_mode('csp'))
        self.assertEqual([s['kind'] for s in r['steps']], ['prepare', 'prepare'])
        self.assertIn('0x607A', r['steps'][0]['note'])
        self.assertIn('0x6060 = 8', r['steps'][1]['note'])

    def test_every_mode_has_a_set_point_step(self):
        for code in cia402.MODES:
            with self.subTest(mode=code):
                steps = cia402._mode_steps(cia402.resolve_mode(str(code)))
                self.assertIn(cia402.MODES[code][0], cia402.SETPOINT_BEFORE_ENABLE)
                self.assertNotIn('0x6060', steps[0]['note'])
        steps = cia402._mode_steps(cia402.resolve_mode('-1'))
        self.assertIn('manufacturer-specific', steps[0]['note'])

    def test_mode_zero_is_refused(self):
        with self.assertRaises(ValueError):
            cia402.plan('switch_on_disabled', mode=cia402.resolve_mode('0'))

    def test_already_there(self):
        r = cia402.plan('switched_on', 'switched_on')
        self.assertEqual(r['steps'], [])
        self.assertIn('Already in', r['notes'][0])

    def test_uncommandable_target(self):
        for target in cia402.UNCOMMANDABLE:
            with self.assertRaises(ValueError):
                cia402.plan('switch_on_disabled', target)

    def test_start_from_a_statusword(self):
        self.assertEqual(cia402.resolve_state('0x0250')[0], 'switch_on_disabled')
        state, notices = cia402.resolve_state('104')
        self.assertEqual(state, 'fault')
        self.assertTrue(notices)
        for text in ('0x0002', '0x10027', '-1'):
            with self.subTest(text=text):
                with self.assertRaises(ValueError):
                    cia402.resolve_state(text)
        with self.assertRaises(ValueError):
            cia402.resolve_state('0x0027', allow_statusword=False)


class OtherObjects(unittest.TestCase):

    def test_supported_modes(self):
        r = cia402.decode_supported_modes(0x03ED)
        self.assertEqual([m['key'] for m in r['modes']],
                         ['pp', 'pv', 'pt', 'hm', 'ip', 'csp', 'csv', 'cst'])
        self.assertEqual(r['notes'], [])
        r = cia402.decode_supported_modes(0x00010010)
        self.assertEqual(len(r['notes']), 3)
        r = cia402.decode_supported_modes(0x0400)  # bit 10: mode 11
        self.assertEqual([m['key'] for m in r['modes']], ['cstca'])
        self.assertEqual(r['notes'], [])

    def test_mode_of_operation(self):
        self.assertEqual(cia402.decode_mode(8)['key'], 'csp')
        self.assertEqual(cia402.decode_mode(-3)['kind'], 'manufacturer')
        self.assertEqual(cia402.decode_mode(0)['kind'], 'none')
        self.assertEqual(cia402.decode_mode(5)['kind'], 'unknown')
        self.assertEqual(cia402.decode_mode(11)['key'], 'cstca')
        self.assertIn('Beckhoff', cia402.decode_mode(11)['notes'][0])
        self.assertEqual(cia402.decode_mode(12)['kind'], 'unknown')

    def test_homing_methods(self):
        cases = {
            0: 'no homing operation',
            1: 'negative limit switch, then index pulse',
            2: 'positive limit switch, then index pulse',
            3: 'positive home switch, then index pulse',
            6: 'negative home switch, then index pulse',
            7: 'home switch with reversal at the positive limit switch, then index pulse',
            10: 'home switch with reversal at the positive limit switch, then index pulse',
            11: 'home switch with reversal at the negative limit switch, then index pulse',
            14: 'home switch with reversal at the negative limit switch, then index pulse',
            17: 'as method 1, without the index pulse',
            30: 'as method 14, without the index pulse',
            33: 'index pulse only, moving negative',
            34: 'index pulse only, moving positive',
            35: 'the current position becomes home, no motion',
            37: 'the current position becomes home, no motion',
        }
        for n, text in cases.items():
            with self.subTest(method=n):
                self.assertEqual(cia402.decode_homing_method(n)['description'], text)
        self.assertEqual(cia402.decode_homing_method(-1)['kind'], 'manufacturer')
        self.assertIn('Never carry one', cia402.decode_homing_method(-4)['notes'][0])
        for n in (15, 16, 31, 32, 36, 38):
            self.assertEqual(cia402.decode_homing_method(n)['kind'], 'reserved')
        self.assertEqual(cia402.decode_homing_method(34)['notes'], [])


def pdo(rx, tx, modes='csp'):
    return cia402.check_pdo(cia402._split_entries(rx), cia402._split_entries(tx),
                            [cia402.resolve_mode(m) for m in modes.split(',')])


def at_level(result, level):
    return [f for f in result['findings'] if f['level'] == level]


class PdoCheck(unittest.TestCase):

    # The smallest mapping each mode runs with, written out here rather than read back
    # from cia402.PDO_RULES.
    GOOD = {
        'pp': (['6040', '607A'], ['6041', '6064']),
        'vl': (['6040', '6042'], ['6041']),
        'pv': (['6040', '60FF'], ['6041', '606C']),
        'pt': (['6040', '6071'], ['6041']),
        'hm': (['6040'], ['6041', '6064']),
        'ip': (['6040', '60C1:01'], ['6041', '6064']),
        'csp': (['6040', '607A'], ['6041', '6064']),
        'csv': (['6040', '60FF'], ['6041', '6064']),
        'cst': (['6040', '6071'], ['6041', '6064']),
        'cstca': (['6040', '6071'], ['6041']),
    }

    def test_a_complete_mapping_raises_nothing(self):
        self.assertEqual(set(self.GOOD), {key for key, _ in cia402.MODES.values()})
        for mode, (rx, tx) in self.GOOD.items():
            with self.subTest(mode=mode):
                r = pdo(rx + ['6060'], tx + ['6061', '603F'], mode)
                self.assertEqual(r['findings'], [])

    def test_quiet_on_mapping_values_for_homing_then_csp(self):
        rx = ['0x60400010', '0x60600008', '0x607A0020', '0x60B10020']
        tx = ['0x60410010', '0x60610008', '0x60640020', '0x60F40020', '0x603F0010']
        self.assertEqual(pdo(rx, tx, 'hm,csp')['findings'], [])

    def test_csp_without_set_point_or_feedback(self):
        r = pdo(['6040'], ['6041'], 'csp')
        self.assertEqual({f['object'] for f in at_level(r, 'error')}, {'0x607A', '0x6064'})

    def test_without_controlword_or_statusword(self):
        r = pdo(['607A'], ['6064'], 'csp')
        self.assertEqual({f['object'] for f in at_level(r, 'error')}, {'0x6040', '0x6041'})

    def test_switching_modes_needs_6060_and_6061(self):
        r = pdo(['6040', '607A'], ['6041', '6064'], 'hm,csp')
        errors = {f['object']: f['message'] for f in at_level(r, 'error')}
        self.assertEqual(set(errors), {'0x6060', '0x6061'})
        self.assertIn('confirms a mode switch', errors['0x6061'])

    def test_6060_written_but_never_confirmed(self):
        r = pdo(['6040', '6060', '607A'], ['6041', '6064'], 'csp')
        self.assertEqual(at_level(r, 'error'), [])
        warnings = at_level(r, 'warning')
        self.assertEqual([f['object'] for f in warnings], ['0x6061'])
        self.assertIn('never confirmed', warnings[0]['message'])

    def test_wrong_direction_is_one_error(self):
        r = pdo(['6040', '607A', '6041'], ['6064'], 'csp')
        errors = at_level(r, 'error')
        self.assertEqual(len(errors), 1)
        self.assertIn('belongs in the TxPDO', errors[0]['message'])

    def test_wrong_length_and_subindex(self):
        r = pdo(['0x60400010', '0x60600010', '0x607A0020'], ['6041', '6064', '6061'], 'csp')
        self.assertEqual([f['message'] for f in at_level(r, 'error')],
                         ['0x6060 Modes of operation is 8 bits, mapped as 16.'])
        r = pdo(['6040:01', '607A'], ['6041', '6064'], 'csp')
        self.assertIn('mapped from subindex 0', at_level(r, 'error')[0]['message'])

    def test_mapped_twice(self):
        r = pdo(['6040', '607A', '607A'], ['6041', '6064'], 'csp')
        self.assertIn('mapped twice', at_level(r, 'warning')[0]['message'])

    def test_padding_is_ignored(self):
        r = pdo(['6040', '0x00000008', '607A', '0x00050008'], ['6041', '6064', '603F'], 'csp')
        self.assertEqual([f['level'] for f in r['findings']], ['note'])  # 0x6060 by SDO

    def test_each_axis_is_checked_on_its_own(self):
        r = pdo(['6040', '607A', '6840', '687A'], ['6041', '6064', '6864'], 'csp')
        self.assertEqual(r['axes'], [1, 2])
        errors = at_level(r, 'error')
        self.assertEqual([(f['object'], f['axis']) for f in errors], [('0x6841', 2)])
        self.assertIn('0x6841 Statusword', errors[0]['message'])

    def test_touch_probe_needs_its_status_and_a_latch(self):
        r = pdo(['6040', '607A', '60B8'], ['6041', '6064'], 'csp')
        self.assertEqual([f['object'] for f in at_level(r, 'warning')], ['0x60B9'])
        r = pdo(['6040', '607A', '60B8'], ['6041', '6064', '60B9'], 'csp')
        self.assertIn('no latched position', at_level(r, 'warning')[0]['message'])
        r = pdo(['6040', '607A', '60B8'], ['6041', '6064', '60B9', '60BA'], 'csp')
        self.assertEqual(at_level(r, 'warning'), [])

    def test_set_point_of_another_mode(self):
        r = pdo(['6040', '607A', '60FF'], ['6041', '6064'], 'csp')
        notes = ' '.join(f['message'] for f in at_level(r, 'note'))
        self.assertIn('0x60FF Target velocity is the set-point of PV/CSV, not of CSP', notes)

    def test_vendor_objects_and_modes(self):
        r = pdo(['6040', '2000'], ['6041'], '-3')
        notes = ' '.join(f['message'] for f in at_level(r, 'note'))
        self.assertIn('0x2000 is manufacturer-specific', notes)
        self.assertIn('Mode -3 is manufacturer-specific', notes)
        self.assertEqual(at_level(r, 'error'), [])

    def test_beckhoff_mdp742_is_named(self):
        r = pdo(['7010:01'], ['6010:01'], 'csp')
        notes = [f['message'] for f in at_level(r, 'note')]
        self.assertTrue(any('MDP742' in n for n in notes))
        self.assertFalse(any('object table' in n for n in notes))
        self.assertIn('0x6040', {f['object'] for f in at_level(r, 'error')})

    def test_entry_formats(self):
        for text in ('6040', '0x6040', '16#6040', '6040h', ' 0X6040 '):
            with self.subTest(text=text):
                self.assertEqual(cia402.parse_entry(text),
                                 {'index': 0x6040, 'sub': None, 'bits': None})
        self.assertEqual(cia402.parse_entry('0x607A:00'),
                         {'index': 0x607A, 'sub': 0, 'bits': None})
        self.assertEqual(cia402.parse_entry('0x60400010'),
                         {'index': 0x6040, 'sub': 0, 'bits': 16})
        self.assertEqual(cia402.parse_entry('60C1_0120'),
                         {'index': 0x60C1, 'sub': 1, 'bits': 32})
        self.assertEqual(len(cia402._split_entries(['6040,607A', '6041'])), 3)

    def test_entry_rejects(self):
        for text in ('xyz', '0x16040', '6040:', '6040:100', '6040:00:10', '0x', '-6040'):
            with self.subTest(text=text):
                with self.assertRaises(ValueError):
                    cia402.parse_entry(text)


class Parsing(unittest.TestCase):

    def test_number_formats(self):
        for text in ('0x1637', '16#1637', '5687', '2#0001_0110_0011_0111',
                     '0b0001011000110111', ' 0X1637 '):
            with self.subTest(text=text):
                self.assertEqual(cia402.parse_number(text), 0x1637)
        self.assertEqual(cia402.parse_number('-12'), -12)

    def test_rejects(self):
        for text in ('1A37', 'abc', '0x', '', '16#xyz', '0x-5', '0x0x5', '0x+5', '+5',
                     '2#102'):
            with self.subTest(text=text):
                with self.assertRaises(ValueError):
                    cia402.parse_number(text)

    def test_signed_and_oversized_words(self):
        value, notices = cia402._word(-1, 16, 'sw')
        self.assertEqual(value, 0xFFFF)
        self.assertIn('0xFFFF', notices[0])
        with self.assertRaises(ValueError):
            cia402._word(0x10000, 16, 'sw')
        self.assertEqual(cia402._signed8(0xF8, 'mode')[0], -8)


class Output(unittest.TestCase):

    def test_text_plan_matches_json(self):
        # What the engineer reads must be what the program computed.
        line = re.compile(r'^\s+\d+\. (write (0x[0-9A-F]{4})|wait)  (?:T(\d+) )?.*->  (.+) '
                          r'\(sw & 0x([0-9A-F]{2}) == 0x([0-9A-F]{2})\)$')
        for start in cia402.STATES:
            for target in COMMANDABLE:
                if target == 'quick_stop_active' and start != 'operation_enabled':
                    continue
                with self.subTest(start=start, target=target):
                    _, text = run_main(['plan', start, target, '--mode', 'csp'])
                    _, js = run_main(['plan', start, target, '--mode', 'csp', '--json'])
                    steps = [s for s in json.loads(js)['steps'] if s['kind'] != 'prepare']
                    rows = [m for m in map(line.match, text.splitlines()) if m]
                    self.assertEqual(len(rows), len(steps))
                    for m, s in zip(rows, steps):
                        self.assertEqual(m.group(2), s['controlword_hex'])
                        self.assertEqual(int(m.group(3)) if m.group(3) else None,
                                         s['transition'])
                        self.assertEqual(m.group(4), s['expect_name'])
                        self.assertEqual(int(m.group(5), 16), s['expect_mask'])
                        self.assertEqual(int(m.group(6), 16), s['expect_value'])

    def test_text_decode_shows_state_bits_and_notes(self):
        _, text = run_main(['decode', 'sw', '0x0068'])
        self.assertIn('treat as Fault', text)
        self.assertIn('   3  fault', text)
        self.assertIn('write 0x0000 (hold bit 7 low)', text)
        _, text = run_main(['decode', 'cw', '0x001F', '--mode', 'pp'])
        self.assertIn('command: Enable operation (T4, T16', text)
        self.assertIn('   4  new set-point (rising edge)', text)
        _, text = run_main(['decode', 'modes', '0x0080'])
        self.assertIn('CSP', text)
        _, text = run_main(['decode', 'mode', '0', '--mode', 'csp'])
        self.assertIn('--mode only applies to sw and cw', text)

    def test_script_is_ascii(self):
        # A Windows console in a legacy code page cannot print anything else.
        with open(os.path.join(SCRIPTS, 'cia402.py'), 'rb') as f:
            f.read().decode('ascii')


class CommandLine(unittest.TestCase):

    CASES = [
        ['decode', 'sw', '0x1637', '--mode', 'pp'],
        ['decode', 'sw', '104'],
        ['decode', 'statusword', '16#0250', '--mode', 'hm'],
        ['decode', 'cw', '0x008F'],
        ['decode', '6040', '0x001F', '--mode', 'csp'],
        ['decode', 'modes', '0x000103ED'],
        ['decode', 'mode', '-3'],
        ['decode', 'method', '-1'],
        ['plan', 'fault', '--mode', 'csp'],
        ['plan', '0x0068'],
        ['plan', 'qsa', 'oe', '--quick-stop-stays'],
        ['plan', 'oe', 'sod'],
        ['pdo', '--mode', 'hm,csp', '--rx', '6040,6060,607A', '--tx', '6041', '6061', '6064'],
    ]

    def run_cli(self, args):
        return subprocess.run([sys.executable, os.path.join(SCRIPTS, 'cia402.py')] + args,
                              capture_output=True)

    def test_runs_and_prints_ascii(self):
        for args in self.CASES:
            with self.subTest(args=args):
                r = self.run_cli(args)
                self.assertEqual(r.returncode, 0, r.stderr)
                r.stdout.decode('ascii')

    def test_json_output_parses(self):
        for args in self.CASES:
            with self.subTest(args=args):
                r = self.run_cli(args + ['--json'])
                self.assertEqual(r.returncode, 0, r.stderr)
                json.loads(r.stdout)

    def test_errors_exit_non_zero(self):
        for args in (['decode', 'sw', '0x10000'], ['decode', 'xx', '1'],
                     ['decode', 'sw', '1A37'], ['plan', 'sod', 'fault'],
                     ['plan', 'sod', '0x0027'], ['plan', 'sod', '_0x27'],
                     ['plan', 'nowhere'], ['plan', 'sod', 'qsa'], ['plan', '0x10027'],
                     ['decode', 'sw', '1', '--mode', 'xyz'],
                     ['pdo', '--mode', 'csp', '--rx', 'xyz'], ['pdo', '--mode', '0'],
                     ['pdo', '--rx', '6040']):
            with self.subTest(args=args):
                r = self.run_cli(args)
                self.assertNotEqual(r.returncode, 0)
                self.assertIn(b'error', r.stderr)

    def test_pdo_check_with_an_error_exits_1(self):
        r = self.run_cli(['pdo', '--mode', 'csp', '--rx', '6040', '--tx', '6041'])
        self.assertEqual(r.returncode, 1)
        self.assertIn(b'0x607A Target position is not in the RxPDO', r.stdout)
        self.assertEqual(r.stderr, b'')


if __name__ == '__main__':
    unittest.main()
