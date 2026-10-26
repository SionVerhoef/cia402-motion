# LinMot (C1250-MI / C1251-MI with the CiA 402 interface)

**Read 2026-10-26**: LinMot "EtherCAT CiA402 Profile Interface", document 0185-1178-E_1V0
(June 2023), for drives C1250-MI-XC-0S/1S and C1251-MI-XC-2S,
https://shop.linmot.com/data/import/Software/0185-1178-E_1V0_MA_EtherCAT-CiA402-MI.pdf.
Sections and pages are given in brackets. LinMot parameters are numbered by UPID. Over SDO they
sit at 0x2000 + UPID [§5.4 p. 58].

## Modes

- **Sections exist for modes 1 (PP), 6 (HM), 8 (CSP) and 10 (CST) only.** A manufacturer mode
  0x8A (−118 as INT8), a cyclic closed-loop torque mode, can be switched at run time through PDO
  0x1604/0x1614. 0x6502 is readable, but the manual gives no value [§3, §4.2.3].
- **0x605A–0x605E are not in the object list.** 0x6085 quick-stop deceleration is [§5.4].
- **0x6007 maps to LinMot's timeout reaction**: ignore, error with Disable voltage, error with
  Quick stop, or error with a move to a position [§6.1.5–6.1.7].

## Profile position

- **Controlword bit 9 (change on set-point) is not supported**: keep it 0 [§3.1 p. 13].
- **Statusword bit 13 (following error) is not supported.** Bit 10 (target reached) is the
  inverse of the drive's internal "motion active", and bit 12 is set-point acknowledge as usual
  [§3.1 p. 13].

## Homing

- **The standard methods 1–35 are not supported.** 0x6098 is writable but mirrors LinMot's own
  homing-mode parameter (UPID 13C4h, value minus 128), and only the vendor values −128 to −111
  exist: −128 the actual position, −127 a search for the mechanical stop in the negative
  direction, −111 no drive homing, and so on. Select the method with the LinMot tool or by those
  numbers [§3.2 p. 13; §5.1.1–5.1.2 pp. 30–31].
- **Both 0x6099 subindices write the same single homing speed** (UPID 13C8h) [§5.4].
- **Halt (bit 8) is not supported in homing.** Bit 4 starts homing, and bits 10 and 12 both high
  mean done [§3.2 p. 14].

## CSP

- **The default is "PV streaming"** (UPID 20C0h = 1): the default RxPDO modules (0x1603, 0x1613,
  0x1614) pair the target position 0x607A with a target velocity 0x60FF. The older "P streaming"
  (0) is still selectable [§3.3 pp. 14–15; §4.2.2, 4.2.5, 4.2.6]. So send a velocity with every
  position, or switch to P streaming. The manual does not say what happens if 0x60FF is left out.
  That gap is our reading.
- With TwinCAT NC, the manual sets the NC velocity output scaling to 125.0 and the NC position
  controller output to 0 [§3.3]. The NC side belongs to **twincat-motion**.

## Units and PDOs

- **Torque and force use 5000 = the drive's maximum**, in 0x6077, 0x60E0 and 0x60E1. This is
  not thousandths of rated [§5.2].
- **0x60FF is scaled to 1 µm/s** by a numerator/denominator parameter pair [§5.2].
- **PDOs are predefined modules.** Free mapping exists only through 0x1620/0x1A20, with 1–8
  entries addressed by UPID [§4.1.2].
