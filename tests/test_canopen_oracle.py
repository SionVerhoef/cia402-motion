"""Cross-check against python-canopen (MIT), whose CiA 402 tables were written
independently of this skill's.

Skipped when canopen is not installed: the skill itself never needs it. CI installs it
and sets CIA402_REQUIRE_CANOPEN=1, so there this check fails instead of skipping.
"""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), 'scripts'))

import cia402  # noqa: E402

try:
    from canopen.profiles.p402 import Homing, OperationMode, State402
except ImportError:
    if os.environ.get('CIA402_REQUIRE_CANOPEN'):
        raise
    State402 = None

# canopen's state names -> ours
NAMES = {
    'NOT READY TO SWITCH ON': 'not_ready_to_switch_on',
    'SWITCH ON DISABLED': 'switch_on_disabled',
    'READY TO SWITCH ON': 'ready_to_switch_on',
    'SWITCHED ON': 'switched_on',
    'OPERATION ENABLED': 'operation_enabled',
    'QUICK STOP ACTIVE': 'quick_stop_active',
    'FAULT REACTION ACTIVE': 'fault_reaction_active',
    'FAULT': 'fault',
}

# canopen's homing status names -> our phases
PHASES = {
    'IN PROGRESS': 'in progress',
    'INTERRUPTED': 'interrupted, or not started',
    'ATTAINED': 'attained, target not reached yet',
    'TARGET REACHED': 'completed',
    'ERROR VELOCITY IS NOT ZERO': 'error, motor still moving',
    'ERROR VELOCITY IS ZERO': 'error, at standstill',
}


def canopen_state(sw):
    """What canopen's BaseNode402.state reports for this statusword."""
    for name, (mask, value) in State402.SW_MASK.items():
        if sw & mask == value:
            return name
    return 'UNKNOWN'


def canopen_homing(sw):
    for name, (mask, value) in Homing.STATES.items():
        if sw & mask == value:
            return name
    return None


@unittest.skipIf(State402 is None, 'python-canopen is not installed')
class AgainstCanopen(unittest.TestCase):

    def test_same_state_for_every_statusword(self):
        for sw in range(0x10000):
            theirs = canopen_state(sw)
            ours = cia402.decode_statusword(sw)
            if theirs == 'UNKNOWN':
                self.assertIsNone(ours['state'], hex(sw))
            else:
                self.assertEqual(ours['state'], NAMES[theirs], hex(sw))

    def test_same_homing_phase_for_every_statusword(self):
        # We report a phase only in Operation enabled, where homing runs.
        hm = cia402.resolve_mode('hm')
        for sw in range(0x10000):
            ours = cia402.decode_statusword(sw, hm)
            if ours['state'] != 'operation_enabled':
                self.assertIsNone(ours['homing']['phase'], hex(sw))
                continue
            ours = ours['homing']['phase']
            theirs = canopen_homing(sw)
            if theirs is None:
                self.assertTrue(ours.startswith('reserved'), hex(sw))
            else:
                self.assertEqual(ours, PHASES[theirs], hex(sw))

    def test_same_homing_method_directions(self):
        # canopen names its method constants by switch and direction.
        for name in dir(Homing):
            if not name.startswith('HM_ON_') or 'MECHANICAL' in name or 'FOLLOWING' in name:
                continue  # negative methods: manufacturer-specific, nothing to compare
            numbers = getattr(Homing, name)
            for n in numbers if isinstance(numbers, tuple) else (numbers,):
                with self.subTest(constant=name, method=n):
                    ours = cia402.decode_homing_method(n)['description']
                    if n > 16 and n < 31:
                        ours = cia402.decode_homing_method(n - 16)['description']
                        self.assertIn('without the index pulse',
                                      cia402.decode_homing_method(n)['description'])
                    for word in ('negative', 'positive'):
                        if word in name.lower():
                            self.assertIn(word, ours)
                    if 'HOME_SWITCH' in name:
                        self.assertIn('home switch', ours)
                    if 'LIMIT_SWITCH' in name:
                        self.assertIn('limit switch', ours)
                    if 'CURRENT_POSITION' in name:
                        self.assertIn('current position', ours)

    def test_same_commanded_transitions(self):
        automatic = {('START', 'NOT READY TO SWITCH ON'),
                     ('NOT READY TO SWITCH ON', 'SWITCH ON DISABLED'),
                     ('FAULT REACTION ACTIVE', 'FAULT')}
        theirs = {(NAMES[a], NAMES[b], cw) for (a, b), cw in State402.TRANSITIONTABLE.items()
                  if (a, b) not in automatic}
        ours = {(t['from'], t['to'], t['controlword']) for t in cia402.TRANSITIONS
                if t['controlword'] is not None}
        self.assertEqual(ours, theirs)

    def test_same_mode_codes_and_support_bits(self):
        for code, (key, _) in cia402.MODES.items():
            with self.subTest(mode=key):
                name = OperationMode.CODE2NAME[code]
                bit = OperationMode.SUPPORTED[name]
                self.assertEqual(bit, 1 << (code - 1))
                modes = cia402.decode_supported_modes(bit)['modes']
                self.assertEqual([m['code'] for m in modes], [code])


if __name__ == '__main__':
    unittest.main()
