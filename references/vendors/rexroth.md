# Bosch Rexroth ctrlX DRIVE (firmware AXS-V-06RS)

**Read 2026-11-08**: Bosch Rexroth, *ctrlX DRIVE Runtime AXS-V-06RS Functions (CAN
Parameters), Application Manual*, R911425360, edition 02 (copyright 2024; document code
DOK-XDRV**-AXS-06VRS*C-AP02-EN-P). Rexroth publishes its manuals through
https://docs.automation.boschrexroth.com. Page numbers in brackets are from this manual.

This page covers **ctrlX DRIVE with firmware AXS-V-06RS over EtherCAT (CoE)** only. The older
IndraDrive / HCS01 family was not read; do not carry anything here over to it.

ctrlX DRIVE is a Sercos-heritage drive with CiA 402 layered on top. Much of what the profile
leaves open is answered by Rexroth's own parameters (0x2xxx), and the drive has its own state
machine *above* CiA 402 that decides whether the profile can run at all.

## A second state machine sits above CiA 402

- **Configuration mode (CM), parameterisation mode (PM), operating mode (OM).** CM allows
  every parameter, PM only some, and only OM accepts command values [p. 84]. The parameters are
  checked on the way to OM; a bad one stops the transition with a command error, and
  0x2B64:06 lists the offending parameters [p. 84].
- **By default this machine is coupled to the EtherCAT states** (0x2BD2:03 = 0): the
  transition to SafeOp runs check C0100 and the transition to Op runs check C5200, which brings
  the drive to OM [p. 98]. A slave that refuses Op is usually failing one of these checks, not
  the EtherCAT configuration.
- **CiA 402 transition 2 (Shutdown) is only taken in OM** [p. 90]. In CM or PM the profile stays
  in Switch on disabled whatever the controlword says.
- **Scaling, absolute/modulo format and the motor/load reference can only be changed in CM**
  [p. 523]. A start-up list that writes them in PreOp works; writing them once the drive is
  running does not.
- **The profile has to be selected.** 0x2890:01 picks the drive profile: 0x0402 for CiA 402,
  0x0000 for "no profile" (no controlword or statusword in the cyclic data), 0xFF00 for
  analog/digital-input control. An invalid choice raises C0203 on the PM → OM step [pp. 92–93].
- **"Easy startup" mode (C4700) ignores the master's command values** [p. 254]. A drive left in
  it by a commissioning session will not follow the PLC.

## CiA 402 state machine

- **Switched on needs DC bus voltage**: transition 3 waits for the control and power sections
  to be ready [pp. 89–90]. With 0x2890:04 bit 3 = 0 the controlword also switches the DC bus
  supply; the default (bit 3 = 1) leaves the supply alone [p. 91].
- **Operation enabled has sub-states**: on entry the drive first waits for magnetisation and
  brake release, and on leaving it brakes, waits and applies the brake [p. 89]. Expect a delay
  between the controlword and motion that the profile does not describe.
- **Whether 0x000F in Ready to switch on goes straight to Operation enabled is not stated.**
  The manual lists transitions 3 and 4 separately [p. 90]. Send 0x0007, wait for Switched on,
  then 0x000F.
- **Quick stop (6 or 7) returns to Operation enabled when bit 2 is set again** (T16), and the
  operation mode that was selected resumes [pp. 90, 806].

## Option codes

| Object | ctrlX DRIVE allows | Default | Differs from the profile |
|---|---|---|---|
| 0x605A quick stop | 0, 2, 3, 6, 7 | not stated | no 1, 5 or 8 |
| 0x605B shutdown | −1, 0 | **−1** | −1 = do what 0x605C says |
| 0x605C disable operation | 0; vendor 0x8000, 0x8001, 0x8002, 0x8004, 0x8008 | not stated | 1 (ramp) is not offered; vendor codes have bit 15 set |
| 0x605D halt | 1, −1 | not stated | −1 = stop as for quick stop |
| 0x605E fault reaction | 0, 2, 3; or a vendor bitfield with bit 15 set | not stated | see below |
| 0x6007 abort connection | 0, 1 | not stated | only "no reaction" or "fault" |

[pp. 91, 753–754]. The vendor codes of 0x605C pick a Rexroth "best possible deceleration":
velocity command reset at the current limit, torque disable, ramp with jerk limit (quick stop
or emergency-stop ramp), or a motor phase short circuit (synchronous motors only) [p. 753].

- **0x605E with bit 15 set is a bitfield**, one field per error class: bits 0–3 for F2/F3/F4
  errors, bits 4–7 for travel-range (F6) errors, bits 8–12 for fatal (F8) errors [pp. 748,
  754]. Treat it as a Rexroth parameter, not a profile option code.
- **Some F8 errors ignore 0x605E** and always disable torque (for example STO while enabled,
  overcurrent, encoder module communication), or always short the motor phases (overvoltage)
  [p. 749].
- **A communication failure (bus stop, PLC stop, invalid process data) is an F4 error** and runs
  the 0x605E reaction [pp. 254, 748].
- **0x6085 = 0, or larger than 0x2302:01, uses 0x2302:01** as the quick-stop deceleration
  [p. 805]. 0x2808:01 bit 2 chooses velocity- or position-controlled quick stop [p. 805].
- **Halt only works in PT, PV, PP and homing** (plus the vendor modes drive-internal
  interpolation and positioning block). **In CSP, CSV and CST, bit 8 does nothing** and the axis
  does not slow down [pp. 803, 806].

## Modes of operation

- **0x6060 accepts 1, 3, 4, 6, 8, 9, 10 and −1** [p. 108]. No vl (2), no IP (7). 0x6502 does
  not appear in the manual; 0x2800:09 lists the modes the current configuration supports
  [p. 100].
- **−1 is one slot, filled by 0x2800:08** with the code of a Rexroth mode: drive-controlled CSP
  (0x0305, synchronises to the master's position on entry), drive-internal interpolation
  (0x0315) or positioning block mode (0x0235, needs a licence) [pp. 107, 170]. If 0x2800:08 is
  0, selecting −1 raises F6007 [p. 107].
- **The manual gives homing as 0x6060 = 5 in one list and 6 in the next** [pp. 107, 108]. 6 is
  the profile value and the one in the 0x6060 table; check 0x2800:09 on the drive.
- **CST (10) is torque control with a velocity limit.** The limits come from 0x60C8/0x60C9,
  0x607F and the axis limits; 0x60CA picks the behaviour, and 0 switches the limit off
  [pp. 132, 134].
- **Torque limits are Rexroth parameters** (0x230C:02–0x230C:05); 0x6072 and 0x6073 do not
  appear in the manual [p. 130].
- **In CSP, statusword bit 10 reports the position window** (following error inside 0x6067 for
  0x6068) [p. 149].
- **CSP checks the step between two successive target positions** against the velocity limits,
  0x607F among them, and raises F4037 if it is too large (or warning E4037 with 0x2820:03
  bit 15) [pp. 149–150]. On entry, 0x607A is compared with the drive's own position command, so
  a stale target in the PDO trips F4037 on enable.
- **A missing CSP target is extrapolated** from the last two [p. 148]. Filter and delay
  parameters (0x2822:01, 0x2832:xx, 0x282A:01) only take effect when the mode is set up again
  [p. 150].

## Profile position

- **Absolute moves need a homed encoder.** Otherwise the set-point is dropped and warning E2054
  is raised; relative moves work without a reference [p. 163].
- **0x6081 is scaled by the feed-rate override 0x282E:01.** At 0 the axis does not move and only
  warning E2055 appears [p. 166]. The same override scales homing speed [p. 576].
- **0x6083 or 0x6084 = 0 uses 0x2302:01; if that is also 0, acceleration is unlimited** [p. 167].
- **Controlword bits 11 and 12 select jog and positioning stop** [p. 167]. Both interrupt the
  move; a new bit-4 edge is needed to position again [pp. 162, 168].
- **When the mode is set up again (after halt, quick stop or re-enable), the drive can carry
  on to the old target without a new bit-4 edge**, finishing a relative move's remaining path
  [p. 168].
- A second set-point while the buffer is full raises F2050; a missing follow-on set-point in
  "change on set-point" mode raises F2051 [pp. 165–166].

## Homing

- **Methods 1–6, 17–22, 33, 34 and 37, plus −1** [pp. 176–177]. No 7–14, 23–30 or 35.
- **−1 is not a hard-stop method.** It means "no preset method": the homing sequence is built
  freely in 0x2500:02 (direction, switch edge, reference-mark use, limit switch as home switch,
  fixed stop) [p. 176]. Compare `../homing.md`: on other drives −1 is a hard-stop method.
- **Two encoders**: 0x2500:02 bit 3 picks the encoder to home. 0x607C is the home offset of
  encoder 1; encoder 2 uses 0x2506 [p. 175].
- **Starting homing clears an existing reference first** [p. 574].
- **The homing speed is 0x6099:01 times the feed-rate override 0x282E:01**, with 0x609A as
  the acceleration [pp. 574, 576]. The end of the sequence is set in
  0x2500:02: stop at once, position to the home offset, or run a fixed path (distance-coded
  encoders) [p. 577].

## Units and scaling

- **No profile factor group.** 0x608F, 0x6092 and 0x6093–0x6097 do not appear in the manual.
  0x6091 is the load gear (motor to load); the feed constant is 0x2390:01 [pp. 522, 532].
- **Scaling is Rexroth's**: type, factor and exponent per quantity in 0x2900 (position), 0x2902
  (velocity), 0x2904 (acceleration) and 0x2906 (torque), with "preferred" presets or free
  factors [pp. 523, 525, 528–531].
- **Preferred presets**: position 0.0001 mm or 0.0001°; velocity 0.001 mm/min, 0.0001 rpm or
  0.000001 rps; acceleration 0.001 mm/s² or 0.001 rad/s²; torque 0.01 Nm, force 1 N, or
  0.1 % [pp. 527–530]. Incremental position (encoder 1, motor side only) is also available
  [pp. 527, 532]. Which preset is the factory setting is not stated.
- **Data can refer to the motor or the load** side [p. 532]. Polarity of position, velocity and
  torque is set in 0x290A [p. 533].
- **Absolute position format wraps** at ±0x2488:02; modulo format runs from 0 to 0x2488:01 and
  is only allowed with rotary motors [pp. 524, 533–534]. In modulo, 0x607F may not exceed
  0x2488:01 divided by 2 ms [p. 535].

## PDO mapping and EtherCAT

- **Free mapping, up to 20 objects and 50 bytes per direction** [pp. 259, 261]. Templates come
  from the ESI; the drive lists mappable objects in 0x2C1B:01 (Rx) and 0x2C1A:01 (Tx) [p. 262].
- **Minimum cycle 250 µs; DC Sync0 only** [pp. 259, 262]. Without a cyclic 0x607A the NC cycle
  comes from 0x60C2 [p. 148].
- **0x2820:02 carries extra position resolution** below the position LSB, for CSP [p. 149].
- **Every emergency message uses error code 0xFF00**, register 0x01, with Rexroth's diagnostic
  number in the manufacturer bytes [p. 262]. Decode the number, not the code. 0x10F3 follows
  ETG.1006 [p. 262].
- **CoE implements CiA 301 version 4.2** [p. 263]. EoE, FoE (firmware in Bootstrap only) and
  FSoE are supported [pp. 261, 263]. The master sets the EoE IP address; do not edit
  0x2C21:04–06 in the drive [p. 262].
- **Port XF21 is EtherCAT IN, XF22 is OUT** [p. 259].
