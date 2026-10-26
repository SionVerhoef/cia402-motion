# Synapticon SOMANET

**Read 2026-10-26**:

- **[OD]** SOMANET Object Dictionary 5.4 (documentation v5.4.73, built 2024-11-12),
  https://synapticon-documentation.s3.eu-west-1.amazonaws.com/SOMANET+Object+Dictionary+5.4.pdf
  (page numbers of 376).
- **[HM]** "Homing modes", https://doc.synapticon.com/node/sw5.1/motion_control/operation_modes/homing_modes.html
  (documentation 5.6.40).
- **[PP]** "Profile position", the profiled-modes page of the same documentation set.

The legacy v4.4 pages list fewer homing methods. The items below are for firmware v5.

## State machine and modes

- **0x605A allows 0, 2 and 6 only.** 0 disables the drive function, 2 stops on the quick-stop
  ramp and goes to Switch on disabled, and 6 stops on the quick-stop ramp and stays in Quick stop
  active [OD p. 273].
- **0x605B, 0x605C, 0x605D and 0x605E are not in the object dictionary**, although the
  controlword text mentions a halt option code [OD].
- **0x000F in Ready to switch on is "Switch on + enable operation"** (T3 and T4). The drive
  moves on to Operation enabled by itself [OD p. 269].
- **Manufacturer modes −1 to −6** (cogging recording, diagnostics, open-loop field, system
  identification, joint torque, impedance). Modes can be switched in Operation enabled. 0x6502 =
  0x000303AD [OD pp. 274–275, 317].

## Profile position

**A move is executed only with controlword bit 5 (change set immediately) = 1.** PP takes one
set-point at a time, with no buffer, and bits 6–7 and 9–15 are marked not applicable [PP]. A
master that queues moves with bit 5 = 0, as on most drives, gets no motion.

## Homing

- **0x6098 allows −4 to −1, 0, 1–14, 17–30, 33, 34, 35 and 37.** 35 is deprecated and the same
  as 37 [OD pp. 300–305].
- **−1 to −4 home on an end stop detected by torque.** −1 is the negative end stop with index,
  −2 the positive end stop with index, −3 negative and −4 positive, homing at an offset from
  0x2005:04. Detection: after a 500 ms hold, demand torque minus holding torque must exceed
  0x2005:03 [OD; HM "Homing method -1,-2,-3 and -4"]. **Synapticon's −1 runs in the opposite
  direction to maxon's −1.**
- Every method except 35 and 37 needs Operation enabled [OD p. 299].

## Units

**0x6091 gear ratio is the ratio between the motor shaft and the shaft carrying the position
encoder**, not a user scaling. 0x6092 feed constant drives a virtual gear [OD p. 299]. Do not
copy factor-group values from another vendor's drive.
