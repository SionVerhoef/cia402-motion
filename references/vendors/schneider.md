# Schneider Electric Lexium 32M (LXM32M)

**Read 2026-11-08**: Schneider Electric, *Lexium 32M Servo Drive User Guide*, 0198441113767,
edition 14 (07/2022). Schneider Electric publishes its manuals at https://www.se.com. Page
numbers in brackets are PDF pages; in this guide they match the printed page numbers.

This is the drive's user guide, not a fieldbus manual. It gives every parameter's CANopen and
EtherCAT index, so it shows where the profile objects sit and what Schneider keeps in its own
objects. For how operating states and modes are switched over the bus, PDO mapping and the
fieldbus-specific objects, it points to the separate fieldbus user guides [pp. 243–245]. Those
were not read: the PDO, CSP/CSV/CST and EtherCAT behaviour below is "not read" for that reason.
Objects at 0x3000 and above are Schneider's own.

## Local or fieldbus control

- **The drive takes its states and modes from either the digital inputs or the bus, never
  both.** DEVcmdinterf (0x3005:01) chooses local (1) or fieldbus (2) control. It can only be
  changed with the power stage off and takes effect after a power cycle [p. 182]. In fieldbus
  control the state machine can only be driven over the bus [p. 244].
- **Profile position, homing and interpolated position are fieldbus-only** [p. 182].
- **Other channels can still command the drive** (the HMI, the commissioning software). Setting
  AccessLock (0x3001:0E) = 1 gives the bus exclusive control; it is not persistent [p. 181].
  The inputs Halt, Fault Reset, Enable, the limit and reference switches and STO stay active
  even then [p. 180].

## State machine

- **Switch on disabled goes to Ready to switch on by itself by default.** DS402compatib
  (0x301B:13) = 0, the factory setting, makes T2 automatic; only with 1 does the drive wait for
  the Shutdown command [pp. 241, 539]. A master that expects to stay in Switch on disabled until
  it sends 0x0006 will see Ready to switch on appear unasked.
- **T2 also needs the motor below 1000 rpm, encoder checked, no undervoltage and STO at 24 V.**
  Above 1000 rpm, for example when the load drives the motor, the drive drops from Ready to
  switch on back to Switch on disabled (T7) [p. 241].
- **T4 (Switched on → Operation enabled) is listed as automatic**, with Enable Operation as an
  alternative condition [p. 241]. The guide does not say whether this applies in fieldbus
  control; treat 0x000F from Ready to switch on as going straight through T3 and T4, and do not
  rely on Switched on staying put.
- **Disable operation (T5) always stops with Halt**, then closes the brake and disables the power
  stage [p. 241]. There is no 0x605C in the guide.
- **Fault reset leaves Quick stop active.** After a quick stop caused by an error of class 1, a
  fault reset goes straight back to Operation enabled [pp. 240–241]. The Enable Operation
  command does the same (T16), but only if the quick stop was triggered over the bus [p. 241].
- **Faults come in classes 0–4, not through 0x605E.** Class 0 keeps moving; 1 quick-stops into
  Quick stop active; 2 quick-stops, closes the brake and disables; 3 disables at once; 4 disables
  at once and needs a power cycle to reset [p. 240]. 0x605E is not in the guide.
- **The Enable input is a second way in.** In fieldbus control it must be assigned to an input
  first; from firmware V01.12 its edge can also reset a fault (IO_FaultResOnEnaInp, 0x3005:34)
  [p. 244].

## Option codes

| Object | Lexium 32M | Default | Differs from the profile |
|---|---|---|---|
| 0x605A quick stop | **not in this guide**: the option code is LIM_QStopReact, 0x3006:18 (whether 0x605A also maps to it is a fieldbus-manual question) | 6 | values −2, −1, 6, 7 |
| 0x605B shutdown | 0, 1 | 0 | also governs a disable request in Operation enabled (T9); firmware ≥ V01.26 |
| 0x605C disable operation | absent | — | T5 always uses Halt |
| 0x605D halt | 1, 3 | 1 | no 2 or 4 |
| 0x605E fault reaction | absent | — | error class decides |

**Quick stop lives in a Schneider object, with Schneider values** [p. 322]. 6 decelerates on the
quick-stop ramp and 7 on the quick-stop current, both staying in Quick stop active, as in the
profile. −1 (ramp) and −2 (current) end in Fault instead. There are no 0–5 or 8. The ramp is
RAMPquickstop (0x3006:12, usr_a, default 6000) and the current limit LIM_I_maxQSTP (0x3011:0D)
[p. 323]. Neither LIM_QStopReact nor 0x605D can be written while a deceleration is running
[pp. 321–322].

**0x605B = 0 switches the power stage off at once; 1 halts first** [p. 242]. The halt itself
uses 0x605D: 1 = deceleration ramp (RAMP_v_dec), 3 = current ramp (LIM_I_maxHalt, 0x3011:0E)
[p. 321].

## Statusword

0x6041 bits 0–6, 9, 10 and 12 are as in the profile [p. 380]. Schneider fills the rest:

- **Bit 7 is an error of class 0**, which does not stop the axis [pp. 240, 380].
- **Bit 8 is "halt request active".**
- **Bit 11 (internal limit active) is not set by anything until DS402intLim (0x301B:1E) chooses
  a source**: current or velocity threshold, position or velocity deviation window, a position
  register channel, a hardware limit switch [pp. 378, 381, 540]. The factory setting is 0, "not
  used".
- **Bits 13–15 are named x_err, x_end and ref_ok** [p. 380]. The guide does not define them
  further; check the fieldbus manual before using them.

## Modes of operation

- **0x6060 values: 1, 3, 4, 6, 7, 8, 9, 10, and Schneider's −1 Jog, −2 Electronic Gear,
  −3 Motion Sequence, −6 Manual Tuning / Autotuning** [p. 535]. No vl (2). The guide describes
  8, 9 and 10 nowhere else; the control-mode table does not list them [p. 182].
- **Interpolated position (7) works only over CAN**, from firmware V01.08. Heartbeat and node
  guarding cannot be used in it, so the master must watch PDO reception itself [p. 288]. It
  needs SyncMechStart (0x3022:05) = 2, the standard CANopen sync mechanism (1 is Schneider's
  CANmotion) [pp. 289–290]. The cycle (0x60C2) is 1–20 ms in 1 ms steps; the drive interpolates
  at 250 µs [pp. 288, 291]. Controlword bit 4 starts cyclic processing, and the first target
  must equal the actual position [p. 292].
- **Switching into profile position is only at standstill** with the DS402 profile, whatever
  PP_OpmChgType says; profile velocity and profile torque can be entered while moving [p. 246].

## Homing

- **Methods 1, 2, 7–14, 17, 18, 23–30, 33, 34 and 35** [p. 296]. No 3–6 or 19–22, no 37, and
  **no negative methods**.
- **0x6098 is not stored.** It defaults to 18 (positive limit switch) after power-up. The
  persistent choice is HMprefmethod, 0x3028:0A [pp. 295–296]. A method written only to 0x6098
  is gone after a power cycle.
- **17–30 do not stop at the switch edge.** After finding the edge, the drive moves on by HMdis
  (0x3028:07, usr_p, default 200) and takes that point as the reference [pp. 297, 300–302].
  The profile puts the reference at the edge. Set HMdis to the distance you want, or the home
  is off by 200 units.
- **35 sets the actual position to HMp_setP (0x301B:16)**, not to 0x607C, and only at standstill
  [p. 303]. After a reference movement the position becomes HMp_home (0x3028:0B) [p. 297].
  0x607C does not appear in the guide.
- **0x6099:01 and :02 are in usr_v** (factory 60 and 6) [p. 299]. Methods 33 and 34 run at the
  slower 0x6099:02 [p. 302].
- **An interrupted reference movement leaves no valid zero**; start again. A multiturn encoder
  has a valid zero at power-up [p. 293]. The guide recommends at least 0.05 revolutions between
  switch edge and index pulse, readable in 0x3028:0F [p. 298].

## Units and scaling

- **Scaling is in Schneider objects, not 0x6091/0x6092 or 0x608F**: position ScalePOSnum/denom
  (0x3006:08/07), velocity ScaleVELnum/denom (0x3006:22/21), ramp ScaleRAMPnum/denom
  (0x3006:31/30) [pp. 196–198]. Change them only with the power stage off.
- **Writing the numerator activates the new factor.** Write the denominator first [pp. 196–198].
- **Factory units: 16384 usr_p per revolution, 1 usr_v = 1 rpm, 1 usr_a = 1 rpm/s** [pp. 196–198].
  Profile objects mapped to Schneider parameters take these units, for example 0x6064 in usr_p
  [p. 292].
- **The position range is ±2²⁸ usr_p at factory scaling** (±16384 revolutions). A movement past
  the end makes the zero invalid [p. 183]. With firmware ≥ V01.04 and PP_ModeRangeLim
  (0x3023:07) = 1 the range wraps, and absolute moves past it are allowed; before V01.04 a
  relative move past the end first set the position to 0 [pp. 184–185]. Re-home after a long
  relative move.

## Touch probe

From firmware V01.16 [pp. 338, 340]: 0x60B8/0x60B9, two probes, on DI0/CAP1 and DI1/CAP2
only. **The trigger-select bits (2–3 and 10–11) are reserved**, so the index pulse cannot be a
trigger. Which encoder the capture reads is set in Cap1Source/Cap2Source (0x300A:0A/0B)
[pp. 338–340].
