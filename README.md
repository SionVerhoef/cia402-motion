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

**Status: v0.1.0.** Built from the profile as vendor manuals and permissive implementations
restate it, and from the vendor documents named on each vendor page. Tested against
independent models and in A/B evals; **never run against a real drive**. What is verified and
what is not: [Status](#status).

**What it has shown so far.** In A/B evals (ten tasks, three runs each), Claude Opus 5.5 and
Claude Haiku 5.5 decoded statuswords and planned enable sequences well without the skill. Where
they went wrong was vendor facts and safety. Without the skill, neither knew that a Beckhoff
EL72x1 can be switched to DS402. Five of six answers accepted a false premise about the Omron
1S. Opus told a user to set a quick-stop option code a Nanotec drive does not have. All three
Haiku 4.5 answers wrote Safe Torque Off as standard PLC code. With the skill, every answer was
right, cited the vendor document and date, and declined the safety function: 27 of 27 on both
models, against 22.5 (Opus) and 18.5 (Haiku 5.5) without it, at about nine times the tokens.
Details, including the tasks that measured nothing: [`evals/results-ab.md`](evals/results-ab.md).

## What is in it

- `SKILL.md`: the rules an agent follows, and where to read next.
- `references/`: the state machine, modes, homing, objects, PDO mapping, units, touch probe,
  errors, CANopen bring-up, a commissioning triage tree, the safety boundary, and one page per
  drive vendor with the deviations from the profile that were found in that vendor's own
  documents. Each claim carries its source and the date it was read.
- `scripts/cia402.py`: the tool below.
- `templates/`: `FB_Cia402Axis`, a Structured Text function block that drives one axis
  through the state machine, the mode switch, homing, quick stop and fault reset, as TwinCAT 3
  files and as one plain `.st`, with PDO mapping tables for CSP and PP. Status and wiring are in
  `templates/README.md`.
- `evals/`: the A/B evals, their grader and its self-test, and the trigger evals for the
  description.

## Install

```bash
# Claude Code
git submodule add https://github.com/SionVerhoef/cia402-motion .claude/skills/cia402-motion
```

Pin a release rather than following `main`, and commit the pin:

```bash
git -C .claude/skills/cia402-motion checkout v0.1.0
git add .claude/skills/cia402-motion
```

A plain `git clone` of your repository leaves a submodule folder empty: clone with
`--recurse-submodules`, or run `git submodule update --init`. Without submodules, unpack a
release zip from [Releases](https://github.com/SionVerhoef/cia402-motion/releases) into the same
folder. Other agents that read skill folders (GitHub Copilot in VS Code from `.github/skills/`,
OpenAI Codex from `.agents/skills/`) should load it the same way; that is untested.

The skill hands questions at its edges to sibling skills by name: **ethercat-diagnostics**,
**ethercat-esi**, **twincat-motion**, **twincat-st** and **twincat-scope**. None is required.
Without them it says which skill would own the question and answers the CiA 402 part.

## The tool

`scripts/cia402.py` needs nothing but Python 3.8 or newer (`py -3` on Windows):

```bash
python3 scripts/cia402.py decode sw 0x0068          # non-standard: treated as Fault, and why
python3 scripts/cia402.py decode sw 0x1637 --mode hm
python3 scripts/cia402.py decode cw 0x001F --mode pp
python3 scripts/cia402.py plan fault --mode csp     # controlword sequence, with the CSP set-up
python3 scripts/cia402.py pdo --mode hm,csp --rx 6040 6060 607A --tx 6041 6061 6064
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
- **`pdo`** checks a PDO mapping against the modes an axis runs in. It flags a missing
  controlword, statusword or set-point, 0x6060 without 0x6061, objects in the wrong direction
  or with the wrong length, and touch probes armed but never read. Each axis of a multi-axis
  device is checked on its own. Entries can be pasted as the 32-bit values read from a mapping
  object. It exits 1 on an error, so it can gate a build.

Add `--json` for machine-readable output.

## Status

Nothing here has been run against a real drive, and nothing here can be: there is no drive
where it is developed. The line between verified and not verified is the most important fact
on this page.

**Verified**

- **`decode` agrees with python-canopen** (MIT, written independently) on the state of all
  65,536 statuswords wherever canopen names one, and on homing phases, commanded transitions,
  mode codes and homing-method directions. Mode 11 is the exception: canopen does not have it.
- **Every `plan` is replayed on an independent model drive** in the tests, and `pdo` has a test
  for each rule.
- **`FB_Cia402Axis` passes twincat-st's reviewer**, `--pedantic` included, with one medium
  finding (CP23: 11 pins, where PLCopen suggests about 10), and its file check.
  Its own Structured Text runs against a simulated drive whose statusword arrives up to three
  cycles late, every scan checked against the state-machine rules. Each of 46 rules broken on
  purpose makes the scenario named for it fail.
- **The tests pass on Linux and Windows, and on Python 3.8.**
- **Agent behaviour in A/B evals** on Opus 5.5 and Haiku 5.5, and the safety refusal on Haiku
  4.5 as well: see above and [`evals/results-ab.md`](evals/results-ab.md).
- **The description fires on CiA 402 questions, not on their neighbours.** In trigger evals on
  Opus 5.5 it fired in 38 of 39 runs of queries it should take and in 2 of 33 runs of
  near-misses (EtherCAT faults, ESI files, PROFIdrive, plain Structured Text), both on a TwinCAT
  NC axis question that sits on the boundary: [`evals/README.md`](evals/README.md#trigger-evals).

**Not verified**

- **No real drive.** `FB_Cia402Axis` has never been compiled in TwinCAT or CODESYS and has never
  driven a motor. Treat it as reviewed, not run; test with reduced torque and speed limits.
- **The vendor pages say what the named document said on the date it was read.** No claim was
  checked on hardware, or against other firmware versions.
- **The CANopen bring-up page** has not been run on a bus.
- **Mode 11 (cyclic synchronous torque with commutation angle)** comes from Beckhoff and TI
  documentation, and nothing independent checks it.
- **Drives without a vendor page**, Kollmorgen AKD among them, were not read. No page means
  nothing was read, not that the drive follows the profile.

## Tests

```bash
python3 -m unittest discover -s tests -v
```

`tests/test_canopen_oracle.py` cross-checks statusword states, homing phases, commanded
transitions, mode codes (all but mode 11, which it lacks) and homing-method directions against
[python-canopen](https://github.com/canopen-python/canopen) when it is installed; CI installs it.

`tests/test_templates.py` runs the function block's own Structured Text against a simulated
drive, through `tests/st_subset.py`, a small interpreter for the subset the template is written
in. Every scenario must keep the state-machine rules, and each rule broken on purpose must make
the scenario named for it fail. CI also runs twincat-st's reviewer and file check on
`templates/`, and `evals/selftest.py`, which checks that the eval grader tells a good answer
from a trapped one.

## Licence

MIT — see [LICENSE](LICENSE). Sources and trademarks: [ATTRIBUTIONS.md](ATTRIBUTIONS.md).
