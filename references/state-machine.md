# The drive state machine (FSA)

Every CiA 402 drive runs the same eight-state machine. The master moves it with the
controlword (0x6040) and reads where it is from the statusword (0x6041). Decoding a single
word is rarely where things go wrong. The **order** is: when to raise a bit, how long to hold
it, and when a state may be left. The rules at the end of this page are the ones that agents
and field code break most often, Opus included.

`scripts/cia402.py plan <state or statusword> [target] --mode <mode>` prints the controlword
sequence for any start and target, with transition numbers and the statusword to wait for.
Use it rather than working a path out by hand.

## States

Each state has its own mask on statusword bits 0–6. Bit 5 (quick stop) is part of the pattern
in four states and a don't-care in the other four. A decoder that masks every state with 0x6F
misreads Fault and Switch on disabled whenever bit 5 happens to be set.

| State | Mask | Value | Power stage | Leaves by |
|---|---|---|---|---|
| Not ready to switch on | 0x4F | 0x00 | off | itself, after self-test (T1) |
| Switch on disabled | 0x4F | 0x40 | off | Shutdown 0x0006 (T2) |
| Ready to switch on | 0x6F | 0x21 | off | Switch on 0x0007 (T3) |
| Switched on | 0x6F | 0x23 | on, no torque | Enable operation 0x000F (T4) |
| Operation enabled | 0x6F | 0x27 | on, motor controlled | Disable operation, Shutdown, Quick stop, Disable voltage |
| Quick stop active | 0x6F | 0x07 | on, braking | itself or Disable voltage (T12); 0x000F (T16) only if 0x605A keeps it here |
| Fault reaction active | 0x4F | 0x0F | as 0x605E says | itself, to Fault (T14) |
| Fault | 0x4F | 0x08 | off | Fault reset, rising edge on bit 7 (T15) |

A statusword that matches no mask is not "unknown". If bit 3 (fault) is set, treat the drive as
faulted, because acting as if it is faulted is the safe reading. A Beckhoff EL7221 in DS402 has
been seen reporting 0x0068 (`vendors/beckhoff.md`). `cia402.py decode sw` reports such a word
fault-first and says which bits clash.

Other statusword bits a diagnosis needs:

- **Bit 4, voltage enabled.** In the profile's meaning, high voltage is present at the power
  stage. If it is 0 in Switch on disabled or Ready to switch on, Switch on (T3) cannot work.
  Check mains, the DC link and the main contactor. maxon EPOS4 uses the bit for "power stage on"
  instead, so there it is 0 until T3 by design (`vendors/maxon.md`).
- **Bit 7, warning.** The drive keeps running. The cause is usually in the drive's own
  diagnostic objects.
- **Bit 9, remote.** 0 can mean a commissioning tool or keypad has control and the controlword
  is ignored. maxon EPOS4 uses the bit differently: see `vendors/maxon.md`.
- **Bit 11, internal limit active.** A set-point or output is being clamped by a position,
  velocity, current or torque limit.
- **Bits 10, 12 and 13** depend on the mode: `modes.md`. **Bits 8, 14 and 15** are
  manufacturer-specific.

## Commands

The command is selected by controlword bits 7, 3, 2, 1 and 0. Bit 2 (quick stop) and bit 1
(enable voltage) are **active-low**: a 0 commands the stop.

| Command | Bits 7 3 2 1 0 | Usual word | Transitions |
|---|---|---|---|
| Shutdown | 0 x 1 1 0 | 0x0006 | 2, 6, 8 |
| Switch on | 0 0 1 1 1 | 0x0007 | 3 |
| Switch on + Enable operation | 0 1 1 1 1 | 0x000F | 3 then 4 |
| Enable operation | 0 1 1 1 1 | 0x000F | 4, 16 |
| Disable operation | 0 0 1 1 1 | 0x0007 | 5 |
| Quick stop | 0 x 0 1 x | 0x0002 | 7, 10, 11 |
| Disable voltage | 0 x x 0 x | 0x0000 | 7, 9, 10, 12 |
| Fault reset | 0 → 1 x x x x | 0x0080 | 15 |

Sent in Ready to switch on, 0x000F is the profile's "Switch on + Enable operation": the drive
takes T3 and T4 in one go. maxon and Synapticon document it. Stepping through 0x0007 first
works on every drive, and is the portable choice.

Every command except Fault reset needs bit 7 = 0. Bit 8 is **halt**, bits 4–6 and 9 are
mode-specific, and bits 11–15 are manufacturer-specific. Write bit 10 as 0.

## Transitions

| T | From → to | Controlword | What happens to the motor |
|---|---|---|---|
| 1 | Not ready to switch on → Switch on disabled | (drive) | — |
| 2 | Switch on disabled → Ready to switch on | 0x0006 | — |
| 3 | Ready to switch on → Switched on | 0x0007 | power stage on |
| 4 | Switched on → Operation enabled | 0x000F | follows the set-point of 0x6061's mode |
| 5 | Operation enabled → Switched on | 0x0007 | stops as 0x605C says |
| 6 | Switched on → Ready to switch on | 0x0006 | power stage off |
| 7 | Ready to switch on → Switch on disabled | 0x0000 | — |
| 8 | Operation enabled → Ready to switch on | 0x0006 | stops as 0x605B says, power stage off |
| 9 | Operation enabled → Switch on disabled | 0x0000 | power stage off at once: coasts, or falls onto its brake (maxon EPOS4 first stops as 0x605B says) |
| 10 | Switched on → Switch on disabled | 0x0000 | power stage off |
| 11 | Operation enabled → Quick stop active | 0x0002 | stops as 0x605A says |
| 12 | Quick stop active → Switch on disabled | 0x0000, or the drive itself | power stage off |
| 13 | any → Fault reaction active | (drive) | as 0x605E says |
| 14 | Fault reaction active → Fault | (drive) | — |
| 15 | Fault → Switch on disabled | 0x0080, rising edge | — |
| 16 | Quick stop active → Operation enabled | 0x000F | only when 0x605A keeps the drive in Quick stop active |

## How the drive stops: option codes

Five objects decide how the motor stops on each way out of Operation enabled. They are INT16;
negative values are manufacturer-specific. Drives implement subsets, so read the drive's own
list (or ask ethercat-esi for the allowed values) before writing one.

| Object | Applies to | Values |
|---|---|---|
| 0x605A quick stop option code | T11 | 0 power stage off (coast) · 1 slow-down ramp · 2 quick-stop ramp · 3 current limit · 4 voltage limit: then Switch on disabled. 5–8: the same four ways to stop, then **stay** in Quick stop active |
| 0x605B shutdown option code | T8 | 0 power stage off · 1 slow-down ramp, then off |
| 0x605C disable operation option code | T5 | 0 power stage off · 1 slow-down ramp, then off |
| 0x605D halt option code | controlword bit 8 | 1 slow-down ramp · 2 quick-stop ramp · 3 current limit · 4 voltage limit; the drive stays in Operation enabled |
| 0x605E fault reaction option code | T13 | 0 power stage off · 1 slow-down ramp · 2 quick-stop ramp · 3 current limit · 4 voltage limit |

The slow-down ramp is the deceleration of the active mode: 0x6084 in PP and PV, and 0x6049 in
VL. Drives differ in what they use in the cyclic modes. The quick-stop ramp is 0x6085 (0x604A in
VL).

The vendor subsets differ enough to break a port: maxon EPOS4 offers only 6, Synapticon 0, 2
and 6, Nanotec's CL3-E 0–2, and Beckhoff's EL72x1 in DS402 has no 0x605A at all. Sources are on
the vendor pages.

**To pause an axis, use halt (bit 8), not quick stop.** Halt keeps the drive in Operation
enabled and the motion resumes when bit 8 drops. Quick stop is for abnormal stops, and whether
0x000F brings the drive back (T16) depends on 0x605A. Neither is a safety function:
`safety-boundary.md`.

## Rules for code that drives the FSA

These are what to check in any master code, PLC function block or script, including your own.
Scouting found each of the first eight broken in generated code that explained the rule
correctly in prose. Rule 9 came from this skill's own template.

1. **One command at a time, confirmed.** Hold each controlword until the statusword shows the
   expected state (write it every cycle if it travels in a PDO). Give every wait a timeout, and
   decode the statusword again when one expires. A new command before the previous transition
   has finished is undefined.
2. **Fault reset is an edge, then a release.** Write bit 7 low, then high, then low again. Wait
   for Switch on disabled, then 0x0006 → 0x0007 → 0x000F. Never hold 0x0080, never OR bit 7 into
   0x000F, and release bit 7 after *every* attempt, failed ones included. If the drive stays in
   Fault, the cause is still there: read 0x603F, and retry a limited number of times with a pause
   between attempts. A bit 7 left high blocks the next command, since every other command needs
   bit 7 = 0.
3. **Never run the reset sequence on an axis that is not in Fault.** Its 0x0000 steps command
   Disable voltage, which in Operation enabled cuts the power stage (T9).
4. **Let a quick stop finish.** Leave Quick stop active only when the motor has stopped, or when
   the drive has moved to Switch on disabled by itself. Never leave it on a timer: Quick stop
   active *is* the ramp. Writing 0x0000 in the middle of the ramp switches the power stage off
   and lets the motor coast. With 0x605A = 5–8 the drive stays in Quick stop active at
   standstill, and then 0x000F (T16) or 0x0000 (T12) is yours to send.
5. **Stop with a ramp, not by cutting power.** From Operation enabled prefer Disable operation
   (T5, 0x605C) or Shutdown (T8, 0x605B). Disable voltage (T9) switches off at once; a hanging
   axis then depends on its brake.
6. **Never pass through Operation enabled on the way to another state.** That puts torque on the
   motor with whatever set-point happens to be live.
7. **Before T4, make the set-point safe**, and switch the mode only with 0x6061 confirmed. In CSP
   that means target position = actual position: `modes.md`.
8. **After a fault or a quick stop, from Switch on disabled, the path is 0x0006 → 0x0007 →
   0x000F.** 0x000F alone does nothing there.
9. **While a 0x000F may still land, leave Switched on and Ready to switch on with 0x0002, not
   0x0000.** This is this skill's recommendation, not the profile's, which allows both words for
   T7 and T10. A cyclic statusword is late. It can show a drive that dropped out by itself
   while a word with bit 3 set was still going out, and that drive is already back in Operation
   enabled. There 0x0000 is T9 and 0x0002 is T11; in the two states shown, both go to Switch on
   disabled.
   - Send 0x0000 once your own words have been without bit 3 for longer than the statusword can
     lag. Time your words, not the state: timed on the state, a drive that ignores bit 2 and a
     late statusword keep the two words chasing each other for ever.
   - If the late statusword then shows Operation enabled, hold 0x0002 until that time is up, and
     if the drive has refused T11 fall back to T5.
   - Abandoning a T4 you just sent is the exception: 0x0007 is T5 if it landed and nothing if it
     did not, so the stop stays on 0x605C.

   It costs three things. The motor stops as 0x605A says, not 0x605C, and 0x605A = 0 coasts as T9
   would. With 0x605A = 5–8 any way down can end in Quick stop active, so it needs the exit of
   rule 4 even if you never ask for a quick stop. A drive that ignores bit 2 reads 0x0002 as
   Shutdown, so it needs the 0x0000 above, and waits in Ready to switch on until then; one that
   climbed back takes T8 (0x605B). Beckhoff's EL72x1 in DS402 reserves bit 2 and has no 0x605A,
   and LinMot's C125x-MI has no 0x605A: their vendor pages do not say what 0x0002 does there, so
   try it.

   The race needs a word with bit 3 in the drive or on its way. A fresh statusword is not enough:
   a 0x000F left standing in 0x6040 still lifts a drive that dropped out. With no such word
   0x0000 is right. `FB_Cia402Axis` keeps this rule, with `tStateTimeout` as the time:
   `../templates/README.md`, *Quick stop*.

`cia402.py plan` follows the first eight and notes rule 9 where its path has T7 or T10. It keeps
0x0000 there, for a caller with no word with bit 3 left to land. `cia402.py decode cw <word>`
names the command a word actually sends, which catches 0x000B (quick stop, because bit 2 is 0)
and 0x008F (bit 7 with the enable bits).
