# Beckhoff EL72x1 servo terminals (EL7201, EL7211, EL7221)

**Read 2026-10-26** in the Beckhoff Information System:

- EL72x1-901x documentation v2.4.0 (2024-10-07), covering EL7201/7211/7221-9014/-9015, at
  `https://infosys.beckhoff.com/content/1033/el72x1-901x/<page>`
- EL72x1-001x v3.0.0 (2024-10-02), covering EL7201/7211-0010/-0011. The pages cited below have
  the same numbers and the same text in both sets.

The -0000/-0001 family uses other pages and was not checked. Page numbers are given in brackets.

## Two profiles, and the terminal ships with the wrong one for a CiA 402 master

- **The terminal ships with Beckhoff's MDP742 drive profile.** -0010 and -9014 are the MDP742
  variants, and -0011 and -9015 the DS402 variants. Both hold the same parameters under
  different names and indices, and both run the CiA 402 state machine [1859307019].
- **In MDP742 there is no 0x6040/0x6041.** The controlword is 0x7010:01 and the statusword
  0x6010:01, with modes of operation at 0x7010:03 and the display at 0x6010:03. Controlword bit 2
  and statusword bit 5 are quick stop (inverted) there. The value list of 0x6010:03 omits 8,
  although CSP can be selected through 0x7010:03 [1877540235, 1877535755]. `cia402.py pdo`
  names MDP742 when a mapping contains 0x7010 or 0x6010.
- **To get the DS402 objects, the EEPROM is updated with the DS402 ESI.** Beckhoff names no
  other way to switch, and the type name changes. The motor XML must match the profile, because
  the objects and process data differ [1859307019]. The update is done from the TwinCAT online
  view (EEPROM Update, choose the ESI) and takes effect after a restart; some settings, such as DC,
  need a power cycle [4348710539]. Beckhoff warns that an update can overwrite calibration data
  kept in the EEPROM, and recommends doing updates with its support and with TwinCAT 3 only, not
  with other masters [402909835]. A non-TwinCAT master therefore either drives MDP742 by its own
  indices, or has the terminal converted once on a TwinCAT 3 PC.
- Page 2671297035 is headed "EL72x1-9014 (DS402)" but lists the DS402 objects. By the variant
  table it should read -9015. Do not identify the variant from that heading.

## In DS402 (-0011, -9015)

From the DS402 object page [1877700363] unless marked otherwise.

- **Cyclic modes only: 8, 9, 10 and 11.** 0x6060 accepts 0x08–0x0B, where 11 is cyclic
  synchronous torque with commutation angle (CSTCA). 0x6502 marks them at bits 7–10. There is no
  PP, PV or homing mode and no homing object, so the master does the homing.
- **0x6060 defaults to 0 and is in no predefined PDO set.** Write it at start-up. It and 0x6061
  exist only as the optional PDOs 0x1608 and 0x1A0E [1859309067, 1877760267].
- **No quick stop.** 0x605A is absent (0x6085 too), and controlword bit 2 and statusword bit 5
  are reserved. Stop through the set-points, then Disable operation. Do not plan on 0x000B or
  T16.
- **0x605E offers only 0 (coast) and 1 (slow-down ramp).**
- **Statusword bits 10 and 12 do not mean what the profile says.** Bit 10 is a TxPDO toggle
  (switched on with 0x60DA bit 0), not target reached. Bit 12 is labelled "target value
  ignored". Read its sense on that page before treating it as "follows the command value". With
  0x60DA bit 1, an input cycle counter appears in bit 13, which 0x6041 otherwise lists as
  reserved.
- **Fixed PDOs, one object each.** Every PDO maps exactly one object and the mappings are
  read-only, so the process image is built by choosing PDOs in 0x1C12/0x1C13. The default
  assignment is the CSV set. Predefined sets [1859309067]:

  | Mode | RxPDOs | TxPDOs |
  |---|---|---|
  | CSV (default) | 0x1600, 0x1601 | 0x1A00, 0x1A01 |
  | CST | 0x1600, 0x1602 | 0x1A00, 0x1A01, 0x1A03 |
  | CSTCA | 0x1600, 0x1602, 0x1603 | 0x1A00 |
  | CSP | 0x1600, 0x1606 (0x607A) | 0x1A00, 0x1A01, 0x1A04 (0x60F4) |

- **Units.** 0x607A and 0x6064 are documented as UINT32 in raw increments, to be scaled by the
  master. The default encoder value is 32 bits: 20 single-turn and 12 multi-turn [3170812811].
  0x60FF (INT32) is scaled by 0x6090: a value equal to 0x6090 is 1 rev/s.
- **Torque is in thousandths of the motor rated *current* 0x6075**, not of rated torque.
  Converting to N·m needs 0x2002:54 (whether a √2 factor applies) and the torque constant
  0x2003:16. The torque-offset RxPDO 0x1605 maps the vendor object 0x2001:11, not 0x60B2.
- **CSTCA**: target torque 0x6071 plus the commutation angle 0x60EA (UINT16, 65536 = 360°
  electrical), in RxPDOs 0x1602 and 0x1603. Its predefined set returns only the statusword, with
  no position feedback [1859316107, 1859309067].
- **Cycle**: 250 µs by default, 125 µs minimum [1877760267]. The sync-mode value documented
  for 0x1C32/0x1C33 (0x4808) has the free-run and SM-synchronous bits clear. That suggests DC
  is required, but this is our reading, not a Beckhoff statement.
- **Enable sequence without NC**, from a page written against TwinCAT 2.11: controlword 0,
  0x80, 6, 7, 0xF. For each mode set 0x6060 and the matching predefined PDO assignment, then
  reload the configuration [1859316107]. The page names no waits. Wait on the statusword for each
  step anyway (`../state-machine.md`).

## The field case

In ICube `ethercat_driver_ros2` issue #163 (closed 2025-03-28, read 2026-10-26,
https://github.com/ICube-Robotics/ethercat_driver_ros2/issues/163), an EL7221-9015 in DS402 sent
statusword 104 (0x0068): fault together with switch on disabled. The driver's strict-mask decoder
rejected it. The reporter made the decoder read fault-first and the axis ran; no root cause was
found. Read such a word as Fault (`../state-machine.md`). With bit 5 reserved on this terminal,
only bits 3 and 6 carry meaning in it.
