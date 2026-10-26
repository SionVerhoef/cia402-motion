# cia402-motion

An agent skill for the CiA 402 (DS402) drive profile on any vendor's drive, over EtherCAT or
CANopen: the state machine, modes of operation and object dictionary, and finding out why a
drive won't reach Operation Enabled.

> **Not affiliated with or endorsed by CAN in Automation e.V., the EtherCAT Technology Group,
> Beckhoff Automation GmbH & Co. KG or PLCopen**, nor by any drive manufacturer named here.
> Product and standard names are used only to describe what this skill works with.
>
> **Safety.** This skill produces engineering suggestions, not validated machine software.
> Motion can crush, cut and kill. Never use its output for safety functions (STO, SS1, SLS,
> safe homing, guard monitoring) — those belong in a certified safety controller configured
> and validated per ISO 13849 / IEC 62061. Review every line, test with reduced torque and
> speed limits, and verify on the real machine before anyone stands near it. Responsibility
> for the machine stays with whoever commissions it.

**Status: early development.** Not ready to install yet. The decoder and planner below are
tested against an independent model of the state machine and against python-canopen; none of
it has been run against a real drive.

## The tool

`scripts/cia402.py` needs nothing but Python 3.8 or newer (`py -3` on Windows):

```bash
python3 scripts/cia402.py decode sw 0x0068          # non-standard: treated as Fault, and why
python3 scripts/cia402.py decode sw 0x1637 --mode hm
python3 scripts/cia402.py decode cw 0x001F --mode pp
python3 scripts/cia402.py plan fault --mode csp     # controlword sequence, with the CSP set-up
```

- **`decode`** reads a statusword (0x6041), controlword (0x6040), supported-modes bitmap
  (0x6502), mode of operation (0x6060/0x6061) or homing method (0x6098). Each state is matched
  with its own mask; a statusword that matches none is read fault-first and flagged instead of
  being called "unknown". With `--mode`, bits 10, 12 and 13 (and controlword 4–6, 9) get their
  meaning in that mode, and in homing mode the homing phase.
- **`plan`** gives the controlwords from one state to another with their transition numbers:
  fault reset as a real rising edge on bit 7, released afterwards; the set-point made safe
  (target = actual in CSP) before the mode switch, which is confirmed on 0x6061; a quick stop
  left to finish rather than cut short; never Disable voltage straight from Operation enabled
  (T9), and never a detour through Operation enabled on the way to another state.

Add `--json` for machine-readable output.

## Tests

```bash
python3 -m unittest discover -s tests -v
```

`tests/test_canopen_oracle.py` cross-checks statusword states, homing phases, commanded
transitions, mode codes and homing-method directions against
[python-canopen](https://github.com/canopen-python/canopen) when it is installed; CI installs it.

## Licence

MIT — see [LICENSE](LICENSE). Sources and trademarks: [ATTRIBUTIONS.md](ATTRIBUTIONS.md).
