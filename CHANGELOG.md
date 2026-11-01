# Changelog

## Unreleased

**Templates**

- `FB_Cia402Axis`: a `bQuickStop` input and a `QuickStop` step, so that a process stop no longer
  needs the template changed. 0x0002 goes out on the same scan and is held, and one scan of the
  input is enough; only a fault reset that has begun ends first. The drive leaves Quick stop
  active as it does after a quick stop of its own, never on a timer, and stays down, through an
  error or a fault reset too, until it is there with `bQuickStop` and `bEnable` both FALSE, so
  that nothing restarts it but a new `bEnable`. Not a safety function.
- A drive that does not take 0x0002 in `tStateTimeout` is 16#8108, and the FB goes on with T5:
  asking for a stop never leaves an axis harder to stop.
- The FB now has 11 pins: twincat-st's reviewer reports CP23 (medium), over PLCopen's suggested
  10. Kept: a stop command belongs on a pin, not inside the process-data struct.
- Fixed a hang in the fault reset. A drive that left Fault by itself before an attempt or in the
  pause between two, a reset taken late for one, left the FB waiting for Fault for ever: `bBusy`
  TRUE, no error, 0x0000, `bQuickStop` ignored. It now ends the reset as after an attempt: Switch
  on disabled clears the error, any other state is 16#8113. Fault reaction active still waits,
  and one scan of another state spends no attempt.
- Fixed T9 and a cut quick stop from one bad statusword. A word that decoded for one scan as
  Fault, Switch on disabled, or on a long stop Switched on or Ready to switch on, got 0x0000 on
  that scan, whatever the drive was really doing. The FB now sends 0x0000 for such a word only if
  the next scan shows the same state, and in Fault keeps bits 0-2 of its last word instead. That
  scan no longer starts a fault reset or T2, steps a set-point or releases a quick stop. The
  error and the way down still start at once, and it can still get T5 or T11. Two equal scans
  are believed, including by `bReset` on a word that shows Fault: see the templates README.
- Fixed T9 on the way down. A drive that dropped out while 0x000F or 0x001F was still going out
  was back in Operation enabled when the late statusword showed the drop, and got 0x0000. The FB
  now leaves Switched on and Ready to switch on with 0x0002 while 0x000F may still come: the
  same transition there and T11, not T9, if the drive has climbed back, and 0x605A then decides
  how the motor stops. `cia402.py plan` still says 0x0000, which is right for a caller with no
  word with bit 3 in the drive or on its way.
- Once its words have been without bit 3 for `tStateTimeout` the FB sends 0x0000. A drive that
  ignores controlword bit 2 therefore still gets down, but a way down waits that long.
- A way down can now end in Quick stop active: on a drive with 0x605A 5–8, set `bQuickStopStays`
  even if `bQuickStop` is never used.

**References**

- `state-machine.md` rule 9: leave Switched on and Ready to switch on with 0x0002, not 0x0000,
  while a 0x000F may still land, with what it costs. Labelled as this skill's recommendation,
  not the profile's. The code eval's expected text follows, and a plain 0x0000 there is not a
  fail.
- `cia402.py plan` keeps 0x0000 for T7 and T10, right for a caller with no word with bit 3 in the
  drive or on its way, and adds a note pointing to rule 9.

## 0.1.0 — 2026-10-29

First release: the CiA 402 drive profile on any vendor's drive, over EtherCAT or CANopen. Built
from public sources; never run against a real drive (README, *Status*).

**Skill**

- `SKILL.md`: the rules, the tool, a routing table and the hand-offs to the sibling skills.
  Never writes a safety function; orders commands the way the profile needs them in code;
  vendor facts carry vendor, document and date; what one drive supports comes from the drive.
  `decode` is down to one line: without the skill, current models decode correctly and go
  wrong on ordering in code and on vendor facts.
- The description: "DS402" and the profile's topics, the vendors with pages, and what belongs to
  twincat-motion, ethercat-diagnostics and ethercat-esi. On Opus 5.5 it fired in 38 of 39 runs
  of the queries it should take and 2 of 33 of the near-misses (`evals/README.md`).
- `references/`: state machine, modes, homing, objects, PDO mapping, units, touch probe,
  errors, CANopen bring-up, commissioning triage, safety boundary, and `vendors/` (deviations
  only, each with vendor, source and date) for Beckhoff EL72x1, HIWIN, Lenze, LinMot, maxon
  EPOS4, Nanotec, Omron 1S and Synapticon, with a porting table across them.

**Tool (`scripts/cia402.py`)**

- `decode`: statusword, controlword, 0x6502, 0x6060/0x6061 and 0x6098. Per-state masks, a
  fault-first reading of non-standard statuswords, mode-specific bits and the homing phase.
  Mode 11 (cyclic synchronous torque with commutation angle) and its 0x6502 bit 10, from
  Beckhoff and TI documentation.
- `plan`: controlword sequence to any state that can be commanded, with transition numbers, an
  edge-triggered fault reset, the set-point made safe before the 0x6061-confirmed mode switch,
  a quick stop left to finish before anything else, and never a detour through Operation
  enabled. 0x000F from Ready to switch on is the profile's Switch on + Enable operation command.
- `pdo`: checks a PDO mapping against the modes of an axis, per axis on a multi-axis device.
  Exit 1 on an error.

**Templates**

- `FB_Cia402Axis`, a function block for one axis, as TwinCAT 3 files (POU and four DUTs) and as
  one plain `.st`, with PDO mapping tables for CSP and PP. It confirms every command on the
  statusword with a timeout, resets faults with an edge on bit 7 that is released after every
  attempt, leaves Quick stop active only at standstill or when the drive does, stops with T5 and
  never T9, holds the set-points safe before T4 and never steps one the enabled drive is
  following, and confirms the mode on 0x6061. Reviewed and run against a simulated drive, never
  compiled and never run on hardware. For a drive that makes the motion itself, or a PLC with no
  motion runtime; where TwinCAT NC or CODESYS SoftMotion can drive the axis, their axis and MC_
  blocks remain the choice.

**Evals**

- A/B round on Opus 5.5 and Haiku 5.5, ten tasks, three runs each: 27 of 27 with the skill on
  both models, against 22.5 and 18.5 without it. The safety refusal held in every skill run,
  Haiku 4.5 included, which wrote Safe Torque Off as PLC code in all three runs without it
  (`evals/results-ab.md`).
- `evals/grade.py` grades each answer right, partly or wrong by its eval's rubric, with negative
  checks that do not punish an answer for naming the trap it rejects. `evals/selftest.py` checks
  it against a good and a trapped answer per eval and every answer it once mis-graded; CI runs it.
- `evals/run_cells.py` runs each cell in an isolated headless session and audits it, now also
  for shell commands that reach outside the cell. Trigger evals for the description
  (`evals/trigger-evals.json`, `evals/run_trigger.py`).
- Scouting: the no-skill baseline on 14 tasks on Opus 5.5, Haiku 5.5 and Haiku 4.5
  (`evals/results-scouting.md`), which set the depth of the references.

**Tests and repository**

- Every plan replayed on an independent model drive; statusword states, homing phases,
  commanded transitions, mode codes and homing-method directions cross-checked against
  python-canopen. `tests/st_subset.py` runs the template's Structured Text against a simulated
  drive whose statusword can arrive up to three cycles late; every scenario keeps the
  state-machine rules, and each rule broken on purpose makes the scenario named for it fail.
- CI on Linux and Windows and on Python 3.8, a leak check for network identities, a
  standalone check, and twincat-st's `st_review.py` and `tcpou.py check` on `templates/`.
- README notices (non-affiliation, safety), `ATTRIBUTIONS.md`, contributor rules.
