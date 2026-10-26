# Nanotec

**Read 2026-10-26**:

- **[CL3]** CL3-E CANopen/USB Technical Manual, version 1.3.1 (firmware FIR-v1626), online at
  https://www.nanotec.com/eu/en/products/manual/m/cl3e-can-usb-en/ (object and mode pages).
- **[NP5]** NP5-20 EtherCAT Technical Manual V1.0.2 (FIR-v1748),
  https://www.nanotec.com/fileadmin/files/Handbuecher/Motorsteuerungen/NP5/NP5_EtherCAT_Technical-Manual_V1.0.2.pdf

## Quick stop

**0x605A allows 0, 1 and 2 only:** 0 immediate stop with short-circuit braking, 1 slow-down
ramp, 2 quick-stop ramp, each ending in Switch on disabled. The preset is 1. A quick stop on these
drives never stays in Quick stop active, so T16 does not exist [CL3 object 0x605A; NP5 §6.2.2
p. 48].

## Profile position

- **Switching into PP with bit 4 already set starts the move without a new edge.** Otherwise bit
  4 needs a 0 → 1 edge as usual [NP5 §7.1.1 p. 57]. The CL3-E PP page describes only the edge.
- **0x60F2 bits 4/5 let the drive clear controlword bit 4 itself** [NP5 §7.1.2 p. 59].

## Homing

- **Negative methods are "homing on block"**: a current-based end-stop search configured in
  0x203A (:01 minimum current, :02 blocking period, :03 detection time). With index: −1, −2,
  −7 to −14. Without: −17, −18, −23 to −30. They follow the figures of the positive methods of
  the same magnitude, so −17 blocks on the negative side and −18 on the positive side. Closed loop
  only [NP5 §7.5.2 pp. 73–74; CL3 "Homing on block"].
- **The current-position method is 35.** The CL3-E preset for 0x6098 is 35, which needs only
  Switched on, and 37 is not mentioned [CL3].

## Other

- **The following-error reaction is set in the manufacturer object 0x3700, not 0x605E.**
  0x6065 = 0xFFFFFFFF switches monitoring off [NP5 §6.2.2 p. 50].
- **Manufacturer modes −1 (clock-direction) and −2 (auto setup).** The mode can be changed at any
  time [NP5 §6.2.1 p. 47, p. 249].
