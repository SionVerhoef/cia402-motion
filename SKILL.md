---
name: cia402-motion
description: "Use for the CiA 402 / DS402 (IEC 61800-7) drive profile on any vendor's servo or stepper drive, over EtherCAT (CoE) or CANopen: the controlword/statusword state machine, a drive stuck in Switch on disabled or Fault, fault reset, quick stop and halt, modes of operation (CSP, CSV, CST, PP, PV, homing) and the 0x6060/0x6061 mode switch, homing methods (0x6098), touch probe, units and gearing, 0x603F error codes, which objects to map per mode (0x6040, 0x6041, 0x607A, 0x6064) and checking a PDO mapping, CANopen NMT/SYNC/PDO bring-up of a 402 node, and vendor deviations (Beckhoff EL72x1 DS402 vs MDP742, maxon EPOS4, Omron 1S, Synapticon, Nanotec, LinMot, Lenze, HIWIN). Not for TwinCAT NC axis configuration or MC_ blocks (use twincat-motion), EtherCAT network faults (use ethercat-diagnostics) or reading a device's ESI file (use ethercat-esi). Never writes safety functions such as STO or SLS. DRAFT: under development."
---

# cia402-motion

> **Draft.** This skill is under development and not ready to install.
>
> **Reference material only. Not for safety functions.** Drive configuration must be
> reviewed and validated by a qualified engineer against the drive's own documentation.

## Goal

Bring a CiA 402 drive through its state machine into Operation enabled in the right mode, and
find out why it will not get there.

**Scope and safety.** Output is a draft for a qualified engineer. Never generate or modify
logic that implements a safety function (STO, SS1, SLS, safe homing); refer to the safety
controller instead. When proposing motion code, always state the assumed units, limits and
enable sequence, and tell the user to test with reduced limits. Never claim code is verified
unless it was run on hardware.

## Rules that override everything else

1. **Never author a safety function.** A controlword sent from a standard PLC is not STO, and a
   quick stop is not a safety stop. Decline, name the hardware route, and offer the functional
   part, labelled as not safety: `references/safety-boundary.md`. This holds when the user has
   no safety PLC and asks anyway.
2. **The order is where code goes wrong, not the bits.** Every rule below was broken in
   generated code whose prose explanation got it right. Check your own code against them:
   - hold each command until the statusword confirms it, with a timeout per transition
   - fault reset: bit 7 low → high → low, *then* 0x0006 → 0x0007 → 0x000F; release bit 7 after
     every attempt; never 0x0080 held, never 0x008F
   - leave Quick stop active only at standstill or when the drive moves to Switch on disabled
     itself, never on a timer
   - CSP: target 0x607A = actual 0x6064 before enabling, after homing, and across a mode switch
   - mode switch: write 0x6060, wait for 0x6061, only then the new mode's bits and set-points
   - from Operation enabled, stop with a ramp (T5, T8), not Disable voltage (T9)

   The full list and the reasons are in `references/state-machine.md`.
3. **Vendor facts carry their source.** A statement about one vendor's drive names the vendor,
   the document and the date it was read, from the `references/vendors/` pages. Never present
   it as the profile, and never carry a manufacturer-specific number (negative homing methods,
   negative modes, option codes outside the profile) from one drive to another.
4. **What *this* drive supports is a device fact, not a guess.** Its modes (0x6502), objects,
   allowed values and mappable or default PDOs come from the drive: ask the **ethercat-esi**
   skill, or read its ESI/EDS file or manual. This skill explains the profile, and says when the
   answer depends on the drive.

## Tool

`scripts/cia402.py` needs only Python 3.8+ (`py -3` on Windows).

```bash
python3 scripts/cia402.py plan 0x0218 --mode csp     # controlwords from here to Operation enabled
python3 scripts/cia402.py plan oe sod                # ...or to any state that can be commanded
python3 scripts/cia402.py pdo --mode hm,csp --rx 6040 6060 607A --tx 6041 6061 6064
```

- **`plan`** gives the controlword sequence from any state, or from a statusword value, to any
  commandable state. It includes transition numbers, the statusword to wait for, and the
  set-point and mode steps for `--mode`. Use it for any sequence advice, and compare it with
  code you write. `--quick-stop-stays` when 0x605A keeps the drive in Quick stop active.
- **`pdo`** checks a mapping against the modes an axis runs in. Exit 1 on an error:
  `references/pdo-mapping.md`.
- `decode sw|cw|modes|mode|method <value> [--mode m]`: for a non-standard statusword such as
  0x0068, or to check bit arithmetic.

`--json` gives machine-readable output.

## Where to read next

Load a reference when the task reaches it, not all of them up front.

| Task | Read |
|---|---|
| Drive won't enable, faults, jumps, won't move, stops by itself | `references/commissioning-triage.md` first |
| States, transitions, fault reset, quick stop, halt, option codes 0x605A–0x605E | `references/state-machine.md` |
| Modes, the mode switch, PP handshake, CSP/CSV/CST rules | `references/modes.md` |
| Homing methods, homing status bits, negative method numbers | `references/homing.md` |
| What an object is, its type, PDO or SDO | `references/objects.md` |
| What to map per mode, checking a mapping, fixed PDOs, multi-axis | `references/pdo-mapping.md` |
| User units, gear and feed, 32-bit travel budget, polarity | `references/units.md` |
| Touch probe / position latch | `references/touch-probe.md` |
| 0x603F, EMCY, warning bit, following error | `references/errors.md` |
| CANopen: NMT, COB-IDs, SYNC, PDO setup, heartbeat | `references/canopen-transport.md` |
| A specific vendor's drive | `references/vendors/README.md`, then the vendor's page |
| STO, SS1, SLS, FSoE, E-stop, any SIL/PL claim | `references/safety-boundary.md` |
| PLC code that drives the state machine itself, where no TwinCAT NC or CODESYS SoftMotion axis will: profile modes, drive-based homing, a PLC without a motion runtime. Start from the template; don't write it fresh | `templates/README.md` ("When to use it" first), then `templates/FB_Cia402Axis.st` or the TwinCAT files |

## Hand-offs

| When | Hand to |
|---|---|
| Slaves not in OP, WcState ≠ 0, frame loss, DC/SYNC0 errors, SDO aborts, mapping rejected | **ethercat-diagnostics** |
| What a particular device supports (modes, objects, ranges, PDOs), or its ESI file | **ethercat-esi** |
| TwinCAT NC axis, MC_ blocks, NC scaling, NC homing; `MC_Power` while the drive is fine | **twincat-motion** |
| Writing or reviewing the PLC code | **twincat-st** (and its reviewer) |
| Diagnosing from a TwinCAT Scope recording | **twincat-scope** |

If a sibling skill is not installed, say which one would own the question and answer only the
CiA 402 part.

## Status

Built from the profile as vendor manuals and permissive implementations restate it, and from
the vendor documents named on each vendor page. `cia402.py` is tested against an independent
model drive and against python-canopen (mode 11 excepted). `FB_Cia402Axis` in `templates/` is
reviewed with twincat-st's `st_review.py` and run against a simulated drive; it has never been
compiled. None of it has been run against a real drive: report at that precision, and say
"reviewed, not run" when you hand out the template.
