"""Tests for scripts/cia402.py. Plain unittest, standard library only.

    python3 -m unittest discover -s tests -v

The planner is checked against a model drive written from the controlword bit rules,
independently of cia402.TRANSITIONS, so a wrong row in that table cannot also make
its own test pass. The cross-check against python-canopen is in test_canopen_oracle.py.
"""
import json
import os
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
    if state == 'not_ready_to_switch_on':
        return 'switch_on_disabled'
    if state == 'fault_reaction_active':
        return 'fault'
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


def replay(test, result, prev_cw, quick_stop_stays):
    """Run a plan's steps through the model drive; return the final state."""
    state = result['from']
    for step in result['steps']:
        if step['kind'] == 'prepare':
            continue
        cw = prev_cw if step['kind'] == 'wait' else step['controlword']
        before = state
        state = model_drive(state, cw, prev_cw, quick_stop_stays)
        prev_cw = cw
        test.assertEqual(state, step['expect'],
                         f'{result["from"]} -> {result["to"]}: step {step} left the model '
                         f'in {state}')
        if step['transition']:
            t = cia402.TRANSITION[step['transition']]
            test.assertEqual((t['from'], t['to']), (before, state))
    return state


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
        # Values from public issue logs (research note); the decodes are our arithmetic.
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
        expect = {'switch_on_disabled': 0x0006, 'ready_to_switch_on': 0x0007,
                  'switched_on': 0x000F, 'fault': 0x0000}
        for key, cw in expect.items():
            with self.subTest(state=key):
                nxt = cia402.decode_statusword(cia402.STATES[key]['value'])['next']
                self.assertEqual(nxt['controlword'], cw)
        self.assertIsNone(cia402.decode_statusword(0x0027)['next'])

    def test_voltage_and_remote_notes(self):
        notes = ' '.join(cia402.decode_statusword(0x0040)['notes'])
        self.assertIn('bit 4', notes)
        self.assertIn('bit 9', notes)
        notes = ' '.join(cia402.decode_statusword(0x0250)['notes'])
        self.assertNotIn('bit 4', notes)
        self.assertNotIn('bit 9', notes)


class ModeSpecificBits(unittest.TestCase):

    def meaning(self, result, bit):
        return result['bits'][bit]['meaning']

    def test_bit_12_follows_the_mode(self):
        for mode, meaning in (('pp', 'set-point acknowledge'), ('hm', 'homing attained'),
                              ('csp', 'drive follows the command value'),
                              ('pv', 'speed is zero'), ('pt', 'unused in this mode')):
            with self.subTest(mode=mode):
                r = cia402.decode_statusword(0x1637, cia402.resolve_mode(mode))
                self.assertEqual(self.meaning(r, 12), meaning)
        self.assertEqual(self.meaning(cia402.decode_statusword(0x1637), 12), 'mode-specific')

    def test_homing_phases(self):
        hm = cia402.resolve_mode('hm')
        for bits, phase in cia402.HOMING_PHASES.items():
            with self.subTest(bits=hex(bits)):
                r = cia402.decode_statusword(0x0027 | bits, hm)
                self.assertEqual(r['homing']['phase'], phase)
        for bits in (0x3000, 0x3400):
            r = cia402.decode_statusword(0x0027 | bits, hm)
            self.assertTrue(r['homing']['phase'].startswith('reserved'))

    def test_mode_by_code_and_vendor_mode(self):
        self.assertEqual(cia402.resolve_mode('8')[0], 'csp')
        key, code, _ = cia402.resolve_mode('-3')
        self.assertIsNone(key)
        self.assertEqual(code, -3)
        r = cia402.decode_statusword(0x1637, cia402.resolve_mode('-3'))
        self.assertIn('not decoded', self.meaning(r, 12))
        with self.assertRaises(ValueError):
            cia402.resolve_mode('5')
        with self.assertRaises(ValueError):
            cia402.resolve_mode('xyz')

    def test_controlword_bits_in_profile_position(self):
        r = cia402.decode_controlword(0x001F, cia402.resolve_mode('pp'))
        self.assertEqual(r['command'], 'Enable operation')
        self.assertEqual(self.meaning(r, 4), 'new set-point (rising edge)')

    def test_reserved_mode_bit_in_csp(self):
        r = cia402.decode_controlword(0x001F, cia402.resolve_mode('csp'))
        self.assertEqual(self.meaning(r, 4), 'reserved in this mode')
        self.assertTrue(any('should be 0' in n for n in r['notes']))


class Controlword(unittest.TestCase):

    def test_commands(self):
        cases = {0x0006: 'Shutdown', 0x0007: 'Switch on / Disable operation',
                 0x000F: 'Enable operation', 0x0000: 'Disable voltage',
                 0x0002: 'Quick stop', 0x0080: 'Fault reset', 0x000E: 'Shutdown',
                 0x0004: 'Disable voltage', 0x000A: 'Quick stop'}
        for cw, command in cases.items():
            with self.subTest(cw=hex(cw)):
                self.assertEqual(cia402.controlword_command(cw)[0], command)

    def test_every_transition_controlword_selects_it(self):
        for t in cia402.TRANSITIONS:
            if t['controlword'] is not None:
                with self.subTest(t=t['id']):
                    self.assertIn(t['id'], cia402.controlword_command(t['controlword'])[1])

    def test_every_value_decodes(self):
        for cw in range(0x10000):
            cia402.decode_controlword(cw)

    def test_bit7_held_high_is_flagged(self):
        notes = ' '.join(cia402.decode_controlword(0x008F)['notes'])
        self.assertIn('Release it', notes)
        self.assertIn('Bits 0-3 are set as well', notes)


class Planner(unittest.TestCase):

    def test_every_plan_reaches_its_target_on_the_model_drive(self):
        for start in cia402.STATES:
            for target in COMMANDABLE:
                for stays in (False, True):
                    for mode in (None, 'csp', 'pp', 'hm'):
                        for prev_cw in (0x0000, 0x0080, 0x000F):
                            with self.subTest(start=start, target=target, stays=stays,
                                              mode=mode, prev=hex(prev_cw)):
                                r = cia402.plan(start, target, cia402.resolve_mode(mode),
                                                stays)
                                self.assertEqual(replay(self, r, prev_cw, stays), target)

    def test_bit7_is_set_only_by_the_reset(self):
        for start in cia402.STATES:
            for target in COMMANDABLE:
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

    def test_disable_avoids_coasting(self):
        r = cia402.plan('operation_enabled', 'switch_on_disabled')
        self.assertEqual([s['transition'] for s in r['steps']], [5, 10])

    def test_quick_stop_return(self):
        r = cia402.plan('quick_stop_active')
        self.assertEqual([s['transition'] for s in r['steps']], [12, 2, 3, 4])
        self.assertTrue(any('--quick-stop-stays' in n for n in r['notes']))
        r = cia402.plan('quick_stop_active', quick_stop_stays=True)
        self.assertEqual([s['transition'] for s in r['steps']], [16])

    def test_mode_set_up_comes_right_before_enable(self):
        r = cia402.plan('switch_on_disabled', mode=cia402.resolve_mode('csp'))
        kinds = [s['kind'] for s in r['steps']]
        self.assertEqual(kinds, ['write', 'write', 'prepare', 'prepare', 'write'])
        self.assertIn('0x6061 reads 8', r['steps'][2]['note'])
        self.assertIn('0x607A', r['steps'][3]['note'])
        self.assertIn('0x6064', r['steps'][3]['note'])
        self.assertEqual(r['steps'][4]['transition'], 4)

    def test_mode_switch_while_enabled(self):
        r = cia402.plan('operation_enabled', mode=cia402.resolve_mode('pp'))
        self.assertTrue(r['steps'])
        self.assertTrue(all(s['kind'] == 'prepare' for s in r['steps']))

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
        with self.assertRaises(ValueError):
            cia402.resolve_state('0x0002')


class OtherObjects(unittest.TestCase):

    def test_supported_modes(self):
        r = cia402.decode_supported_modes(0x03ED)
        self.assertEqual([m['key'] for m in r['modes']],
                         ['pp', 'pv', 'pt', 'hm', 'ip', 'csp', 'csv', 'cst'])
        self.assertEqual(r['notes'], [])
        r = cia402.decode_supported_modes(0x00010010)
        self.assertEqual(len(r['notes']), 3)

    def test_mode_of_operation(self):
        self.assertEqual(cia402.decode_mode(8)['key'], 'csp')
        self.assertEqual(cia402.decode_mode(-3)['kind'], 'manufacturer')
        self.assertEqual(cia402.decode_mode(0)['kind'], 'none')
        self.assertEqual(cia402.decode_mode(5)['kind'], 'reserved')

    def test_homing_methods(self):
        self.assertEqual(cia402.decode_homing_method(-1)['kind'], 'manufacturer')
        self.assertIn('Never carry one', cia402.decode_homing_method(-4)['notes'][0])
        for n in (35, 37):
            self.assertIn('current position', cia402.decode_homing_method(n)['description'])
        self.assertEqual(cia402.decode_homing_method(17)['description'],
                         'as method 1, without the index pulse')
        for n in (15, 16, 31, 32, 36, 38):
            self.assertEqual(cia402.decode_homing_method(n)['kind'], 'reserved')


class Parsing(unittest.TestCase):

    def test_number_formats(self):
        for text in ('0x1637', '16#1637', '5687', '2#0001_0110_0011_0111',
                     '0b0001011000110111', ' 0X1637 '):
            with self.subTest(text=text):
                self.assertEqual(cia402.parse_number(text), 0x1637)

    def test_rejects(self):
        for text in ('1A37', 'abc', '0x', '', '16#xyz'):
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
    ]

    def run_cli(self, args):
        return subprocess.run([sys.executable, os.path.join(SCRIPTS, 'cia402.py')] + args,
                              capture_output=True)

    def test_text_output_is_ascii(self):
        # A Windows console in a legacy code page cannot print anything else.
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
                     ['plan', 'sod', '0x0027'], ['plan', 'nowhere'],
                     ['decode', 'sw', '1', '--mode', 'xyz']):
            with self.subTest(args=args):
                r = self.run_cli(args)
                self.assertNotEqual(r.returncode, 0)
                self.assertIn(b'error', r.stderr)


if __name__ == '__main__':
    unittest.main()
