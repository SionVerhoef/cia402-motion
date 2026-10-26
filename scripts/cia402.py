#!/usr/bin/env python3
"""Decode CiA 402 drive words and plan state-machine transitions.

    cia402.py decode sw 0x1637 --mode pp      statusword (0x6041), mode-aware
    cia402.py decode cw 0x001F --mode pp      controlword (0x6040)
    cia402.py decode modes 0x03ED             supported drive modes (0x6502)
    cia402.py decode mode -3                  modes of operation (0x6060 / 0x6061)
    cia402.py decode method 35                homing method (0x6098)
    cia402.py plan fault                      Fault -> Operation enabled
    cia402.py plan 0x0250 switched_on         from a statusword to a state
    cia402.py plan sod --mode csp             with the mode switch and the CSP set-up

--json prints the same result for a program. A value is decimal, 0x or 16# hex, or
0b or 2# binary; underscores are ignored, so 2#0001_0110 works.

Standard library only, so it runs on an engineering PC with nothing but Python 3.8.
Bit numbers, object indices and code values are facts of the profile; every label
and note here is original wording.
"""
import argparse
import heapq
import json
import sys


# --- State machine ----------------------------------------------------------------

# Each state is recognised by its own mask on statusword bits 0-6. Bit 5 (quick stop)
# belongs to the pattern in four states and is a don't-care in the other four, so a
# single 0x6F mask misreads Fault and Switch on disabled whenever bit 5 is set.
STATES = {
    'not_ready_to_switch_on': {
        'name': 'Not ready to switch on', 'mask': 0x4F, 'value': 0x00,
        'hint': 'Booting and self-testing; the drive leaves by itself (T1). Staying here '
                'is not a controlword problem.',
    },
    'switch_on_disabled': {
        'name': 'Switch on disabled', 'mask': 0x4F, 'value': 0x40,
        'hint': 'Power stage off. Send 0x0006 (Shutdown, T2) to reach Ready to switch on.',
    },
    'ready_to_switch_on': {
        'name': 'Ready to switch on', 'mask': 0x6F, 'value': 0x21,
        'hint': 'Shutdown accepted, power stage still off. Send 0x0007 (Switch on, T3).',
    },
    'switched_on': {
        'name': 'Switched on', 'mask': 0x6F, 'value': 0x23,
        'hint': 'High voltage on, drive function still disabled: no torque. Send 0x000F '
                '(Enable operation, T4).',
    },
    'operation_enabled': {
        'name': 'Operation enabled', 'mask': 0x6F, 'value': 0x27,
        'hint': 'Motor under control; the drive follows the set-points of the mode shown '
                'in 0x6061.',
    },
    'quick_stop_active': {
        'name': 'Quick stop active', 'mask': 0x6F, 'value': 0x07,
        'hint': 'Braking as 0x605A says. Let the stop finish: unless 0x605A keeps the '
                'drive here, it moves to Switch on disabled by itself (T12). Only at '
                'standstill: 0x0000 leaves (T12), and 0x000F returns to Operation enabled '
                '(T16) if 0x605A keeps the drive here.',
    },
    'fault_reaction_active': {
        'name': 'Fault reaction active', 'mask': 0x4F, 'value': 0x0F,
        'hint': 'Running its fault reaction (0x605E); it moves to Fault by itself (T14).',
    },
    'fault': {
        'name': 'Fault', 'mask': 0x4F, 'value': 0x08,
        'hint': 'Fault latched, power stage off. Read 0x603F, remove the cause, then reset '
                'with a rising edge on controlword bit 7 (T15).',
    },
}

ALIASES = {
    'nrtso': 'not_ready_to_switch_on', 'sod': 'switch_on_disabled',
    'rtso': 'ready_to_switch_on', 'so': 'switched_on', 'oe': 'operation_enabled',
    'qsa': 'quick_stop_active', 'fra': 'fault_reaction_active',
}

# The drive enters these by itself; no controlword selects them.
UNCOMMANDABLE = ('not_ready_to_switch_on', 'fault_reaction_active', 'fault')

# Numbered as in the profile. A controlword of None means the drive takes the
# transition by itself; '*' is any state. The notes on transitions that leave
# Operation enabled say how the motor stops.
TRANSITIONS = [
    {'id': 1, 'from': 'not_ready_to_switch_on', 'to': 'switch_on_disabled',
     'controlword': None, 'command': 'automatic',
     'note': 'The drive leaves by itself once its self-test passes.'},
    {'id': 2, 'from': 'switch_on_disabled', 'to': 'ready_to_switch_on',
     'controlword': 0x0006, 'command': 'Shutdown', 'note': ''},
    {'id': 3, 'from': 'ready_to_switch_on', 'to': 'switched_on',
     'controlword': 0x0007, 'command': 'Switch on', 'note': ''},
    {'id': 4, 'from': 'switched_on', 'to': 'operation_enabled',
     'controlword': 0x000F, 'command': 'Enable operation', 'note': ''},
    {'id': 5, 'from': 'operation_enabled', 'to': 'switched_on',
     'controlword': 0x0007, 'command': 'Disable operation',
     'note': 'The motor stops as the disable-operation option code (0x605C) says.'},
    {'id': 6, 'from': 'switched_on', 'to': 'ready_to_switch_on',
     'controlword': 0x0006, 'command': 'Shutdown', 'note': ''},
    {'id': 7, 'from': 'ready_to_switch_on', 'to': 'switch_on_disabled',
     'controlword': 0x0000, 'command': 'Disable voltage', 'note': ''},
    {'id': 8, 'from': 'operation_enabled', 'to': 'ready_to_switch_on',
     'controlword': 0x0006, 'command': 'Shutdown',
     'note': 'The motor stops as the shutdown option code (0x605B) says.'},
    {'id': 9, 'from': 'operation_enabled', 'to': 'switch_on_disabled',
     'controlword': 0x0000, 'command': 'Disable voltage',
     'note': 'The power stage switches off at once and the motor is no longer driven; '
             'a hanging axis depends on its brake.'},
    {'id': 10, 'from': 'switched_on', 'to': 'switch_on_disabled',
     'controlword': 0x0000, 'command': 'Disable voltage', 'note': ''},
    {'id': 11, 'from': 'operation_enabled', 'to': 'quick_stop_active',
     'controlword': 0x0002, 'command': 'Quick stop',
     'note': 'The motor stops as the quick-stop option code (0x605A) says, typically on '
             'the quick-stop deceleration 0x6085.'},
    {'id': 12, 'from': 'quick_stop_active', 'to': 'switch_on_disabled',
     'controlword': 0x0000, 'command': 'Disable voltage',
     'note': 'Also happens by itself at the end of the quick stop, unless 0x605A keeps '
             'the drive in Quick stop active.'},
    {'id': 13, 'from': '*', 'to': 'fault_reaction_active',
     'controlword': None, 'command': 'automatic', 'note': 'A fault occurs, in any state.'},
    {'id': 14, 'from': 'fault_reaction_active', 'to': 'fault',
     'controlword': None, 'command': 'automatic',
     'note': 'The drive moves on by itself when its fault reaction ends.'},
    {'id': 15, 'from': 'fault', 'to': 'switch_on_disabled',
     'controlword': 0x0080, 'command': 'Fault reset',
     'note': 'Acts on the rising edge of bit 7, and only once the cause is gone.'},
    {'id': 16, 'from': 'quick_stop_active', 'to': 'operation_enabled',
     'controlword': 0x000F, 'command': 'Enable operation',
     'note': 'Only possible when 0x605A keeps the drive in Quick stop active.'},
]
TRANSITION = {t['id']: t for t in TRANSITIONS}

# T9 always cuts the power stage at once, so the planner avoids it: T5 and T8 stop the
# motor as 0x605C / 0x605B say, which at least can be a ramp.
STEP_COST = {9: 3}


# --- Words and modes ----------------------------------------------------------------

STATUSWORD_BITS = {
    0: 'ready to switch on',
    1: 'switched on',
    2: 'operation enabled',
    3: 'fault',
    4: 'voltage enabled',
    5: 'quick stop (0 = quick stop active)',
    6: 'switch on disabled',
    7: 'warning',
    8: 'manufacturer-specific',
    9: 'remote',
    10: 'target reached (meaning depends on the mode)',
    11: 'internal limit active',
    12: 'mode-specific',
    13: 'mode-specific',
    14: 'manufacturer-specific',
    15: 'manufacturer-specific',
}

CONTROLWORD_BITS = {
    0: 'switch on',
    1: 'enable voltage',
    2: 'quick stop (0 = quick stop)',
    3: 'enable operation',
    4: 'mode-specific',
    5: 'mode-specific',
    6: 'mode-specific',
    7: 'fault reset (rising edge)',
    8: 'halt',
    9: 'mode-specific',
    10: 'reserved',
    11: 'manufacturer-specific',
    12: 'manufacturer-specific',
    13: 'manufacturer-specific',
    14: 'manufacturer-specific',
    15: 'manufacturer-specific',
}

MODE_SW_BITS = (10, 12, 13)
MODE_CW_BITS = (4, 5, 6, 9)

# Modes of operation (0x6060 / 0x6061). Bit (code - 1) of 0x6502 says a drive
# supports the mode. Negative codes are manufacturer-specific.
MODES = {
    1: ('pp', 'Profile position'),
    2: ('vl', 'Velocity'),
    3: ('pv', 'Profile velocity'),
    4: ('pt', 'Profile torque'),
    6: ('hm', 'Homing'),
    7: ('ip', 'Interpolated position'),
    8: ('csp', 'Cyclic synchronous position'),
    9: ('csv', 'Cyclic synchronous velocity'),
    10: ('cst', 'Cyclic synchronous torque'),
}
MODE_CODE = {key: code for code, (key, _) in MODES.items()}

# What the mode-specific bits mean in each mode. A bit a mode does not list is unused
# there (statusword) or reserved and to be written 0 (controlword). VL is left out:
# this tool does not decode its ramp-function bits.
MODE_BITS = {
    'pp': {
        'sw': {10: 'target reached', 12: 'set-point acknowledge', 13: 'following error'},
        'cw': {4: 'new set-point (rising edge)', 5: 'change set immediately',
               6: 'relative target (0 = absolute)', 9: 'change on set-point'},
    },
    'pv': {'sw': {10: 'target reached', 12: 'speed is zero', 13: 'max slippage error'},
           'cw': {}},
    'pt': {'sw': {10: 'target reached'}, 'cw': {}},
    'hm': {
        'sw': {10: 'target reached', 12: 'homing attained', 13: 'homing error'},
        'cw': {4: 'homing operation start (rising edge; 1 -> 0 interrupts)'},
    },
    'ip': {'sw': {10: 'target reached', 12: 'interpolation active'},
           'cw': {4: 'enable interpolation'}},
    'csp': {'sw': {12: 'drive follows the command value', 13: 'following error'},
            'cw': {}},
    'csv': {'sw': {12: 'drive follows the command value'}, 'cw': {}},
    'cst': {'sw': {12: 'drive follows the command value'}, 'cw': {}},
}

# Homing progress in mode HM: statusword bits 13, 12 and 10 under mask 0x3400.
HOMING_PHASES = {
    0x0000: 'in progress',
    0x0400: 'interrupted, or not started',
    0x1000: 'attained, target not reached yet',
    0x1400: 'completed',
    0x2000: 'error, motor still moving',
    0x2400: 'error, at standstill',
}

# Before Operation enabled - and before a mode switch while enabled - the set-point
# must already be one the drive can follow without moving. Keyed by mode.
SETPOINT_BEFORE_ENABLE = {
    'csp': 'Copy the actual position (0x6064) into the target position (0x607A) and '
           'keep sending it every cycle. With target != actual the drive goes for the '
           'target at once: the axis jumps, or trips on following error.',
    'vl': 'Set the target velocity (0x6042) to 0.',
    'csv': 'Set the target velocity (0x60FF) to 0.',
    'pv': 'Set the target velocity (0x60FF) to 0.',
    'cst': 'Set the target torque (0x6071) to 0.',
    'pt': 'Set the target torque (0x6071) to 0.',
    'pp': 'Keep controlword bit 4 low; a move starts later on its rising edge.',
    'hm': 'Select the homing method in 0x6098 (speeds 0x6099, acceleration 0x609A).',
    'ip': 'Keep controlword bit 4 (enable interpolation) low until set-points are ready.',
}
AFTER_ENABLE = {
    'pp': 'Each move: write 0x607A, raise bit 4, wait for statusword bit 12 (set-point '
          'acknowledge), then clear bit 4.',
    'hm': 'Start homing with a rising edge on bit 4 and keep it 1 until homing ends: '
          'done when statusword bits 12 and 10 are both 1, failed when bit 13 is 1.',
    'csp': 'Start the trajectory from the actual position: the master sends a new target '
           'every cycle.',
}
GENERIC_SETPOINT = ('Before enabling, the set-point of the mode in 0x6061 must not cause '
                    'motion (in CSP: target 0x607A = actual 0x6064). Pass --mode for the '
                    'exact steps.')
CYCLIC_NOTE = ('Cyclic synchronous modes usually run on a synchronised bus (EtherCAT '
               'distributed clocks, or CANopen SYNC) with the interpolation period (0x60C2) '
               'equal to the cycle; check which synchronisation this drive requires. Sync '
               'errors are a network problem, not a state-machine one.')
WAIT_NOTE = ('Hold each controlword until the statusword shows the expected state (keep '
             'writing it every cycle if it travels in a PDO), give every wait a timeout, '
             'and decode the statusword again when one expires.')


# --- Parsing ------------------------------------------------------------------------

def parse_number(text):
    """An integer from decimal, 0x / 16# hex or 0b / 2# binary text."""
    s = text.strip().replace('_', '').lower()
    negative = s.startswith('-')
    if negative:
        s = s[1:]
    base, digits = 10, s
    for prefix, b in (('0x', 16), ('16#', 16), ('0b', 2), ('2#', 2)):
        if s.startswith(prefix):
            base, digits = b, s[len(prefix):]
            break
    # Check the digits ourselves: int() would also accept a sign or a second prefix.
    allowed = {10: '0123456789', 16: '0123456789abcdef', 2: '01'}[base]
    if not digits or any(c not in allowed for c in digits):
        hint = ' Hex needs a 0x or 16# prefix.' if base == 10 else ''
        raise ValueError(f'not a number: {text!r}.{hint}')
    value = int(digits, base)
    return -value if negative else value


def _word(value, bits, label):
    """Fit value into an unsigned word, reading a negative one as a signed read-out."""
    top = 1 << bits
    if value < -(top >> 1) or value >= top:
        raise ValueError(f'{label} is {bits} bits; {value} does not fit')
    notices = []
    if value < 0:
        notices.append(f'{value} read as a signed {bits}-bit value: the word is '
                       f'0x{value & (top - 1):0{bits // 4}X}')
    return value & (top - 1), notices


def _signed8(value, label):
    if value < -128 or value > 255:
        raise ValueError(f'{label} is a signed 8-bit value; {value} does not fit')
    if value > 127:
        return value - 256, [f'{value} (0x{value:02X}) read as a signed byte: {value - 256}']
    return value, []


def resolve_mode(text):
    """(key, code, name) for a mode given as pp/csp/... or as its 0x6060 code."""
    if text is None:
        return None
    t = str(text).strip().lower()
    if t in MODE_CODE:
        code = MODE_CODE[t]
    else:
        try:
            code, _ = _signed8(parse_number(t), 'a mode')
        except ValueError:
            raise ValueError(f'unknown mode {text!r}: use one of '
                             f'{", ".join(MODE_CODE)} or a 0x6060 code') from None
    if code in MODES:
        key, name = MODES[code]
        return key, code, name
    if code < 0:
        return None, code, f'manufacturer-specific mode {code}'
    if code == 0:
        return None, 0, 'no mode'
    raise ValueError(f'mode {code} is not in this tool\'s table')


def resolve_state(text, allow_statusword=True):
    """(state key, notices) from a name, an alias or, if allowed, a statusword value."""
    t = text.strip().lower().replace(' ', '_').replace('-', '_')
    if t in STATES:
        return t, []
    if t in ALIASES:
        return ALIASES[t], []
    names = f'a state name or one of {", ".join(ALIASES)}'
    if not allow_statusword:
        raise ValueError(f'unknown state {text!r}: use {names}')
    try:
        value, notices = _word(parse_number(text), 16, 'the statusword')
    except ValueError:
        raise ValueError(f'unknown state {text!r}: use {names}, or a statusword '
                         f'value') from None
    if notices:
        raise ValueError(f'{notices[0]}; give the statusword as an unsigned value')
    result = decode_statusword(value)
    if result['state']:
        return result['state'], []
    if result['treat_as']:
        return result['treat_as'], [result['notes'][0]]
    raise ValueError(f'statusword {result["hex"]} is not a state: {result["notes"][0]}')


# --- Decoding -----------------------------------------------------------------------

def match_state(sw):
    """The state key whose mask matches, or None."""
    for key, state in STATES.items():
        if sw & state['mask'] == state['value']:
            return key
    return None


def _nearest_state(sw):
    """(state to treat a non-standard statusword as, why). Fault first: bit 3 is set
    only in the fault states, and acting as if faulted is the safe reading."""
    if sw & 0x08:
        key = 'fault_reaction_active' if sw & 0x07 == 0x07 else 'fault'
        others = [b for b in (0, 1, 2, 6) if sw & (1 << b)]
        return key, (f'Not a defined state: the fault bit (3) is set together with '
                     f'{_bits(others)}. Treat it as {STATES[key]["name"]}: read 0x603F '
                     f'and reset as from Fault.')
    if sw & 0x40:
        others = [b for b in (0, 1, 2) if sw & (1 << b)]
        return 'switch_on_disabled', (
            f'Not a defined state: switch on disabled (bit 6) is set together with '
            f'{_bits(others)}. Treat it as Switch on disabled.')
    low = sw & 0x07
    if low in (0x01, 0x03):
        key = 'ready_to_switch_on' if low == 0x01 else 'switched_on'
        return key, (f'Not a defined state: bits 0-2 say {STATES[key]["name"]}, but '
                     f'quick stop (bit 5) is 0, which that state does not allow. Treat it '
                     f'as {STATES[key]["name"]} and check how the drive reports bit 5.')
    return None, (f'Not a defined state: bits 2-0 are {low:03b}, which no state uses '
                  f'(they switch on in order 0, 1, 2). Check that this really is 0x6041.')


def _bits(bits):
    """'bit 6' or 'bits 0, 1 and 6'."""
    if len(bits) == 1:
        return f'bit {bits[0]}'
    return 'bits ' + ', '.join(str(b) for b in bits[:-1]) + f' and {bits[-1]}'


def _bit_table(value, generic, mode_bits, word, mode):
    key = mode[0] if mode else None
    rows = []
    for bit in range(16):
        meaning = generic[bit]
        if bit in mode_bits and mode:
            if key in MODE_BITS:
                unused = 'unused in this mode' if word == 'sw' else 'reserved in this mode'
                meaning = MODE_BITS[key][word].get(bit, unused)
            else:
                meaning = 'mode-specific (not decoded for this mode)'
        rows.append({'bit': bit, 'set': bool(value & (1 << bit)), 'meaning': meaning})
    return rows


def _mode_out(mode):
    if not mode:
        return None
    return {'key': mode[0], 'code': mode[1], 'name': mode[2]}


def decode_statusword(sw, mode=None):
    """Decode 0x6041. mode is the result of resolve_mode(), or None."""
    state = match_state(sw)
    notes = []
    treat_as = None
    if state:
        notes.append(STATES[state]['hint'])
    else:
        treat_as, why = _nearest_state(sw)
        notes.append(why)
    current = state or treat_as
    bits = _bit_table(sw, STATUSWORD_BITS, MODE_SW_BITS, 'sw', mode)
    is_set = {row['bit'] for row in bits if row['set']}

    if state == 'fault_reaction_active':
        notes.append('Read 0x603F for the error code.')
    if 4 not in is_set and current in ('switch_on_disabled', 'ready_to_switch_on'):
        notes.append('Voltage enabled (bit 4) is 0: no high voltage at the power stage, '
                     'and Switch on (T3) needs it. Check the mains or DC-link supply '
                     '(a drive that never sets bit 4 can ignore this).')
    if 7 in is_set:
        notes.append('Warning (bit 7): the drive keeps running; the cause is in its own '
                     'diagnostic objects.')
    if 9 not in is_set:
        notes.append('Remote (bit 9) is 0: the drive may not be acting on the controlword '
                     '(a commissioning tool or keypad has control). On maxon EPOS4 the bit '
                     'shows instead whether the network is in NMT Operational.')
    if 11 in is_set:
        notes.append('Internal limit active (bit 11): a set-point or output is being '
                     'clamped by a position, velocity, current or torque limit.')
    vendor = sorted(is_set & {8, 14, 15})
    if vendor:
        notes.append(f'Manufacturer-specific {_bits(vendor)} set: the meaning is in the '
                     f'drive manual.')

    homing = None
    if mode and mode[0] == 'hm':
        phase = sw & 0x3400
        homing = {'bits': f'0x{phase:04X}', 'phase': None}
        if state == 'operation_enabled':
            homing['phase'] = HOMING_PHASES.get(phase, 'reserved: attained and error both '
                                                       'set')
            notes.append(f'Homing: {homing["phase"]}.')
        else:
            notes.append('Homing runs only in Operation enabled: bits 10, 12 and 13 report '
                         'no homing progress in this state.')
    elif mode and mode[0] in ('pp', 'csp') and 13 in is_set:
        notes.append('Following error (bit 13): the position has deviated more than 0x6065 '
                     'for longer than 0x6066.')
    elif not mode and is_set & set(MODE_SW_BITS):
        notes.append(f'Mode-specific {_bits(sorted(is_set & set(MODE_SW_BITS)))} set: pass '
                     f'--mode to decode.')

    out = {
        'object': '0x6041', 'value': sw, 'hex': f'0x{sw:04X}', 'mode': _mode_out(mode),
        'state': state, 'state_name': STATES[state]['name'] if state else None,
        'nonstandard': state is None, 'treat_as': treat_as,
        'bits': bits, 'homing': homing, 'notes': notes, 'next': None,
    }
    if current and current != 'operation_enabled':
        first = plan(current)['steps'][0]
        out['next'] = {k: first[k] for k in ('kind', 'controlword', 'transition', 'command')}
    return out


def controlword_command(cw):
    """(command, transitions it can trigger) selected by bits 7, 3, 2, 1, 0."""
    if cw & 0x80:
        return 'Fault reset', [15]
    if not cw & 0x02:
        return 'Disable voltage', [7, 9, 10, 12]
    if not cw & 0x04:
        return 'Quick stop', [7, 10, 11]
    if not cw & 0x01:
        return 'Shutdown', [2, 6, 8]
    if not cw & 0x08:
        return 'Switch on / Disable operation', [3, 5]
    return 'Enable operation', [4, 16]


def decode_controlword(cw, mode=None):
    """Decode 0x6040. The command depends on the state it is sent in, so every
    transition the bit pattern can trigger is listed."""
    command, transitions = controlword_command(cw)
    bits = _bit_table(cw, CONTROLWORD_BITS, MODE_CW_BITS, 'cw', mode)
    is_set = {row['bit'] for row in bits if row['set']}
    notes = []
    if cw & 0x80:
        notes.append('Fault reset acts on the 0 -> 1 edge of bit 7, and only in Fault. '
                     'Release it afterwards: every other command needs bit 7 = 0, so a '
                     'bit 7 held high can block the next transition.')
        if cw & 0x0F:
            notes.append(f'Bits 0-3 are set as well (0x{cw & 0x0F:X}): the profile has no '
                         f'command with bit 7 = 1 other than Fault reset, so what a drive '
                         f'does with them is not defined.')
    if command == 'Enable operation':
        notes.append('Sent in Ready to switch on, 0x000F means Switch on + Enable operation '
                     '(T3, then T4), as maxon EPOS4 documents.')
    if 8 in is_set:
        notes.append('Halt (bit 8): the drive decelerates as 0x605D says and stays in '
                     'Operation enabled.')
    if 10 in is_set:
        notes.append('Bit 10 is reserved and should be 0.')
    vendor = sorted(is_set & set(range(11, 16)))
    if vendor:
        notes.append(f'Manufacturer-specific {_bits(vendor)} set: see the drive manual.')
    mode_set = sorted(is_set & set(MODE_CW_BITS))
    if mode_set and not mode:
        notes.append(f'Mode-specific {_bits(mode_set)} set: pass --mode to decode.')
    elif mode_set and mode[0] in MODE_BITS:
        reserved = [b for b in mode_set if b not in MODE_BITS[mode[0]]['cw']]
        if reserved:
            notes.append(f'In {mode[2]}, {_bits(reserved)} should be 0: reserved there, '
                         f'and a drive that needs it set is non-standard.')
        if mode[0] == 'pp' and 4 in is_set:
            notes.append('New set-point is taken on the rising edge of bit 4: wait for '
                         'statusword bit 12, then clear bit 4.')
    return {
        'object': '0x6040', 'value': cw, 'hex': f'0x{cw:04X}', 'mode': _mode_out(mode),
        'command': command, 'transitions': transitions, 'bits': bits, 'notes': notes,
    }


def decode_supported_modes(value):
    """Decode 0x6502: bit (code - 1) set means mode `code` is supported."""
    modes = [{'code': code, 'key': key, 'name': name}
             for code, (key, name) in MODES.items() if value & (1 << (code - 1))]
    notes = []
    reserved = [b for b in [4] + list(range(10, 16)) if value & (1 << b)]
    if reserved:
        notes.append(f'{_bits(reserved).capitalize()} set: not in this tool\'s table '
                     f'(reserved, or a mode from a later edition of the profile).')
    vendor = [b for b in range(16, 32) if value & (1 << b)]
    if vendor:
        notes.append(f'Manufacturer-specific modes, {_bits(vendor)}: see the drive manual.')
    if not modes:
        notes.append('No standard mode is supported.')
    return {'object': '0x6502', 'value': value, 'hex': f'0x{value:08X}', 'modes': modes,
            'notes': notes}


def decode_mode(code):
    """Decode a 0x6060 / 0x6061 value (signed 8-bit)."""
    if code in MODES:
        key, name = MODES[code]
        kind = 'standard'
    elif code == 0:
        key, name, kind = None, 'no mode assigned', 'none'
    elif code < 0:
        key, name, kind = None, 'manufacturer-specific', 'manufacturer'
    else:
        key, name, kind = None, 'not in this tool\'s table', 'unknown'
    notes = []
    if kind == 'manufacturer':
        notes.append('Negative modes are manufacturer-specific: the same number can mean '
                     'different things on different drives. Look it up in this drive\'s '
                     'manual.')
    if kind == 'unknown':
        notes.append('Reserved, or a mode added in a later edition of the profile: check '
                     'the drive manual.')
    return {'object': '0x6060 / 0x6061', 'value': code, 'key': key, 'name': name,
            'kind': kind, 'notes': notes}


def decode_homing_method(n):
    """Classify a 0x6098 homing method number."""
    notes = []
    if n < 0:
        kind, text = 'manufacturer', 'manufacturer-specific'
        notes.append('Negative methods are defined by each manufacturer, and the same '
                     'number means different things on different drives. Never carry one '
                     'over to another vendor: look it up in this drive\'s manual.')
    elif n == 0:
        kind, text = 'none', 'no homing operation'
    elif n in (1, 2):
        kind = 'standard'
        side = 'negative' if n == 1 else 'positive'
        text = f'{side} limit switch, then index pulse'
    elif 3 <= n <= 6:
        kind = 'standard'
        side = 'positive' if n <= 4 else 'negative'
        text = f'{side} home switch, then index pulse'
    elif 7 <= n <= 14:
        kind = 'standard'
        side = 'positive' if n <= 10 else 'negative'
        text = f'home switch with reversal at the {side} limit switch, then index pulse'
    elif 17 <= n <= 30:
        kind = 'standard'
        text = f'as method {n - 16}, without the index pulse'
    elif n in (33, 34):
        kind = 'standard'
        text = f'index pulse only, moving {"negative" if n == 33 else "positive"}'
    elif n in (35, 37):
        kind = 'standard'
        text = 'the current position becomes home, no motion'
        notes.append('35 and 37 mean the same; drives accept one or both.')
    else:
        kind, text = 'reserved', 'reserved'
    if kind == 'standard' and n <= 30:
        notes.append('Which switch edge and which side of it count differ between '
                     'neighbouring numbers: check the method diagram in the drive manual.')
    return {'object': '0x6098', 'value': n, 'kind': kind, 'description': text,
            'notes': notes}


# --- Planning -----------------------------------------------------------------------

def _step(kind, controlword=None, transition=None, command='', expect=None, note=''):
    state = STATES.get(expect)
    return {
        'kind': kind, 'controlword': controlword,
        'controlword_hex': None if controlword is None else f'0x{controlword:04X}',
        'transition': transition, 'command': command, 'expect': expect,
        'expect_name': state['name'] if state else None,
        'expect_mask': state['mask'] if state else None,
        'expect_value': state['value'] if state else None,
        'note': note,
    }


def _transition_step(t):
    kind = 'write' if t['controlword'] is not None else 'wait'
    return _step(kind, t['controlword'], t['id'], t['command'], t['to'], t['note'])


def _shortest_path(start, target, quick_stop_stays):
    """The cheapest list of commanded transitions from start to target. Ties go to the
    lowest transition numbers, so a plan is always the same. A path never passes through
    Operation enabled on its way somewhere else: that would put torque on the motor with
    whatever set-point happens to be live."""
    edges = [t for t in TRANSITIONS
             if t['controlword'] is not None and (t['id'] != 16 or quick_stop_stays)
             and (t['to'] != 'operation_enabled' or target == 'operation_enabled')]
    queue = [(0, [], start)]
    done = set()
    while queue:
        cost, path, state = heapq.heappop(queue)
        if state == target:
            return [TRANSITION[i] for i in path]
        if state in done:
            continue
        done.add(state)
        for t in edges:
            if t['from'] == state:
                heapq.heappush(queue, (cost + STEP_COST.get(t['id'], 1), path + [t['id']],
                                       t['to']))
    raise ValueError(f'no commanded path from {STATES[start]["name"]} to '
                     f'{STATES[target]["name"]}')


def _mode_steps(mode):
    """Set-point first, then the mode: switched while enabled, the drive follows the
    new mode's set-point the moment 0x6061 changes."""
    key, code, name = mode
    setpoint = SETPOINT_BEFORE_ENABLE.get(
        key, 'Set this mode\'s set-point so it cannot cause motion (a manufacturer-specific '
             'mode: see the drive manual).')
    return [
        _step('prepare', note=setpoint),
        _step('prepare', note=f'Write 0x6060 = {code} ({name}) and wait until 0x6061 reads '
                              f'{code}. Until it does, the mode-specific bits still belong '
                              f'to the old mode.'),
    ]


def plan(start, target='operation_enabled', mode=None, quick_stop_stays=False):
    """Steps that take a drive from state `start` to state `target`. mode is the result
    of resolve_mode(), or None; quick_stop_stays says 0x605A keeps the drive in Quick
    stop active, which is what makes T16 possible."""
    if target in UNCOMMANDABLE:
        raise ValueError(f'{STATES[target]["name"]} cannot be commanded: the drive enters '
                         f'it by itself')
    if target == 'quick_stop_active' and start not in ('operation_enabled',
                                                       'quick_stop_active'):
        raise ValueError(f'Quick stop active is reached only from Operation enabled (T11). '
                         f'From {STATES[start]["name"]} a quick stop leads to Switch on '
                         f'disabled; planning one would enable the motor just to stop it')
    if mode and mode[1] == 0:
        raise ValueError('mode 0 is no mode: give the mode to switch to')
    steps, notes = [], []
    state = start
    if state == 'not_ready_to_switch_on':
        steps.append(_transition_step(TRANSITION[1]))
        state = 'switch_on_disabled'
    if state == 'fault_reaction_active':
        steps.append(_transition_step(TRANSITION[14]))
        state = 'fault'
    if state == 'fault':
        steps += [
            _step('write', 0x0000, None, 'hold bit 7 low', 'fault',
                  'Bit 7 low first, so that the next write is a rising edge.'),
            _step('write', 0x0080, 15, 'Fault reset', 'switch_on_disabled',
                  'If the drive stays in Fault, the cause is still there: read 0x603F.'),
            _step('write', 0x0000, None, 'release bit 7', 'switch_on_disabled',
                  'Pause a few cycles before the next command. A defensive habit: the '
                  'open-source KickCAT master holds 0 after every reset so that the drive '
                  'does not fault again.'),
        ]
        state = 'switch_on_disabled'
    if state == 'quick_stop_active' and target != state:
        # Disable voltage in the middle of the quick-stop ramp would cut the power stage
        # and let the motor coast, so first let the stop finish.
        if quick_stop_stays:
            steps.append(_step('prepare', note='Wait until the quick stop has brought the '
                                               'motor to a standstill.'))
        else:
            steps.append(_step(
                'wait', None, 12, 'automatic', 'switch_on_disabled',
                'Let the quick stop finish: unless 0x605A keeps the drive in Quick stop '
                'active, it moves to Switch on disabled by itself once the motor has '
                'stopped. If it stays, pass --quick-stop-stays.'))
            state = 'switch_on_disabled'

    path = _shortest_path(state, target, quick_stop_stays)
    for t in path:
        step = _transition_step(t)
        if t['to'] == 'operation_enabled':
            if mode:
                steps += _mode_steps(mode)
            else:
                step['note'] = ' '.join(filter(None, (t['note'], GENERIC_SETPOINT)))
        steps.append(step)
    if start == target == 'operation_enabled' and mode:
        steps += _mode_steps(mode)

    if start == target and not steps:
        notes.append(f'Already in {STATES[target]["name"]}: nothing to send.')
    if mode and target != 'operation_enabled':
        notes.append('--mode only adds steps on the way into Operation enabled.')
    if start == 'quick_stop_active' and target == 'operation_enabled' and not quick_stop_stays:
        notes.append('This goes through Switch on disabled. Direct return with 0x000F (T16) '
                     'works only when 0x605A keeps the drive in Quick stop active; pass '
                     '--quick-stop-stays if it does.')
    if mode and target == 'operation_enabled':
        if mode[0] in AFTER_ENABLE:
            notes.append(AFTER_ENABLE[mode[0]])
        if mode[0] in ('csp', 'csv', 'cst'):
            notes.append(CYCLIC_NOTE)
    if any(s['kind'] != 'prepare' for s in steps):
        notes.append(WAIT_NOTE)
    return {'from': start, 'from_name': STATES[start]['name'], 'to': target,
            'to_name': STATES[target]['name'], 'mode': _mode_out(mode),
            'steps': steps, 'notes': notes}


# --- Output -------------------------------------------------------------------------

def _print_bits(result):
    set_rows = [row for row in result['bits'] if row['set']]
    if set_rows:
        print('set bits:')
        for row in set_rows:
            print(f'  {row["bit"]:>2}  {row["meaning"]}')
    else:
        print('set bits: none')


def _print_notes(notes):
    if notes:
        print('notes:')
        for note in notes:
            print(f'  - {note}')


def _mode_suffix(result):
    return f', mode {result["mode"]["name"]}' if result.get('mode') else ''


def render_statusword(r):
    print(f'statusword {r["hex"]} ({r["value"]}){_mode_suffix(r)}')
    if r['state']:
        print(f'state: {r["state_name"]}')
    elif r['treat_as']:
        print(f'state: none (non-standard); treat as {STATES[r["treat_as"]]["name"]}')
    else:
        print('state: none (non-standard)')
    _print_bits(r)
    _print_notes(r['notes'])
    nxt = r['next']
    if nxt and nxt['kind'] == 'write':
        print(f'next toward Operation enabled: write 0x{nxt["controlword"]:04X} '
              f'({nxt["command"]}) - full sequence: cia402.py plan {r["hex"]}')
    elif nxt:
        print(f'next toward Operation enabled: {nxt["kind"]} ({nxt["command"]})')


def render_controlword(r):
    print(f'controlword {r["hex"]} ({r["value"]}){_mode_suffix(r)}')
    ts = ', '.join(f'T{t}' for t in r['transitions'])
    print(f'command: {r["command"]} ({ts}, depending on the state)')
    _print_bits(r)
    _print_notes(r['notes'])


def render_supported_modes(r):
    print(f'supported modes {r["hex"]} ({r["value"]})')
    for m in r['modes']:
        print(f'  {m["code"]:>2}  {m["key"].upper():<4} {m["name"]}')
    _print_notes(r['notes'])


def render_mode(r):
    print(f'mode of operation {r["value"]}: {r["name"]}'
          + (f' ({r["key"].upper()})' if r['key'] else ''))
    _print_notes(r['notes'])


def render_method(r):
    print(f'homing method {r["value"]}: {r["description"]} ({r["kind"]})')
    _print_notes(r['notes'])


def render_plan(r):
    print(f'plan: {r["from_name"]} -> {r["to_name"]}{_mode_suffix(r)}')
    for n, s in enumerate(r['steps'], 1):
        if s['kind'] == 'prepare':
            print(f'  {n}. prepare')
        else:
            t = f'T{s["transition"]} ' if s['transition'] else ''
            what = (f'write {s["controlword_hex"]}' if s['kind'] == 'write' else 'wait')
            print(f'  {n}. {what}  {t}{s["command"]}  ->  {s["expect_name"]} '
                  f'(sw & 0x{s["expect_mask"]:02X} == 0x{s["expect_value"]:02X})')
        if s['note']:
            print(f'       {s["note"]}')
    _print_notes(r['notes'])


# --- Command line -------------------------------------------------------------------

WHAT = {
    'sw': 'sw', 'statusword': 'sw', '6041': 'sw', '0x6041': 'sw',
    'cw': 'cw', 'controlword': 'cw', '6040': 'cw', '0x6040': 'cw',
    'modes': 'modes', 'supported': 'modes', '6502': 'modes', '0x6502': 'modes',
    'mode': 'mode', '6060': 'mode', '0x6060': 'mode', '6061': 'mode', '0x6061': 'mode',
    'method': 'method', '6098': 'method', '0x6098': 'method',
}


def run_decode(what, text, mode_text):
    kind = WHAT.get(what.lower())
    if kind is None:
        raise ValueError(f'cannot decode {what!r}: use sw, cw, modes, mode or method')
    mode = resolve_mode(mode_text)
    value = parse_number(text)
    if kind == 'sw':
        value, notices = _word(value, 16, 'the statusword')
        result, render = decode_statusword(value, mode), render_statusword
    elif kind == 'cw':
        value, notices = _word(value, 16, 'the controlword')
        result, render = decode_controlword(value, mode), render_controlword
    elif kind == 'modes':
        value, notices = _word(value, 32, '0x6502')
        result, render = decode_supported_modes(value), render_supported_modes
    elif kind == 'mode':
        value, notices = _signed8(value, '0x6060')
        result, render = decode_mode(value), render_mode
    else:
        value, notices = _signed8(value, '0x6098')
        result, render = decode_homing_method(value), render_method
    if mode and kind not in ('sw', 'cw'):
        notices.append('--mode only applies to sw and cw.')
    result['notes'] = notices + result['notes']
    return result, render


def run_plan(start_text, target_text, mode_text, quick_stop_stays):
    start, notices = resolve_state(start_text)
    target, _ = resolve_state(target_text, allow_statusword=False)
    result = plan(start, target, resolve_mode(mode_text), quick_stop_stays)
    result['notes'] = notices + result['notes']
    return result, render_plan


def main(argv=None):
    parser = argparse.ArgumentParser(
        description='Decode CiA 402 drive words and plan state-machine transitions.')
    sub = parser.add_subparsers(dest='verb', required=True)

    p = sub.add_parser('decode', help='decode a statusword, controlword, 0x6502, 0x6060 '
                                      'or 0x6098 value')
    p.add_argument('what', help='sw | cw | modes | mode | method (or the object index)')
    p.add_argument('value', help='decimal, 0x / 16# hex, or 0b / 2# binary')
    p.add_argument('--mode', help='mode of operation for the mode-specific bits: '
                                  'pp, pv, pt, hm, ip, csp, csv, cst or a 0x6060 code')
    p.add_argument('--json', action='store_true', help='machine-readable output')

    p = sub.add_parser('plan', help='controlword sequence from one state to another')
    p.add_argument('start', help='state name or alias (sod, rtso, so, oe, qsa, fra, '
                                 'nrtso, fault) or a statusword value')
    p.add_argument('target', nargs='?', default='operation_enabled',
                   help='state name or alias (default: operation_enabled)')
    p.add_argument('--mode', help='mode to switch to on the way into Operation enabled')
    p.add_argument('--quick-stop-stays', action='store_true',
                   help='0x605A keeps the drive in Quick stop active, so T16 is allowed')
    p.add_argument('--json', action='store_true', help='machine-readable output')

    args = parser.parse_args(argv)
    try:
        if args.verb == 'decode':
            result, render = run_decode(args.what, args.value, args.mode)
        else:
            result, render = run_plan(args.start, args.target, args.mode,
                                      args.quick_stop_stays)
    except ValueError as e:
        parser.error(str(e))
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        render(result)
    return 0


if __name__ == '__main__':
    sys.exit(main())
