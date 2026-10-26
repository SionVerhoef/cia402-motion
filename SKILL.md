---
name: cia402-motion
description: "Use for the CiA 402 / DS402 (IEC 61800-7) drive profile on any vendor's servo or stepper drive, over EtherCAT (CoE) or CANopen: the controlword/statusword state machine, why a drive is stuck in Switch On Disabled or Fault, modes of operation (CSP, CSV, CST, PP, PV, homing), CoE object dictionary entries (0x6040, 0x6041, 0x6060, 0x6061, 0x607A) and PDO mapping. Not for TwinCAT NC axis configuration or MC_ blocks (use twincat-motion) or EtherCAT network faults (use ethercat-diagnostics). DRAFT: under development."
---

# cia402-motion

> **Draft.** This skill is under development and not ready to install.
>
> **Reference material only. Not for safety functions.** Drive configuration must be
> reviewed and validated by a qualified engineer against the drive's own documentation.

## Goal

Bring a CiA 402 drive through its state machine into Operation Enabled in the right mode,
and diagnose why it will not get there.

**Scope and safety.** Output is a draft for a qualified engineer. Never generate or modify
logic that implements a safety function (STO, SS1, SLS, safe homing); refer to the safety
controller instead. When proposing motion code, always state the assumed units, limits and
enable sequence, and tell the user to test with reduced limits. Never claim code is verified
unless it was run on hardware.

## Tool

`scripts/cia402.py` decodes and plans deterministically. Run it instead of working out bits
by hand:

```bash
python3 scripts/cia402.py decode sw 0x1637 --mode pp   # statusword: state, mode bits, next step
python3 scripts/cia402.py decode cw 0x001F --mode pp   # controlword: which command it is
python3 scripts/cia402.py decode modes 0x03ED          # 0x6502 supported modes
python3 scripts/cia402.py decode mode -3               # 0x6060 / 0x6061 mode of operation
python3 scripts/cia402.py decode method -1             # 0x6098 homing method
python3 scripts/cia402.py plan 0x0218 --mode csp       # controlwords from here to Operation enabled
```

`--json` gives machine-readable output. Standard library only; on Windows use `py -3`.
