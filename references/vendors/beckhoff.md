# Beckhoff

Beckhoff's documentation shows only two of these families as CiA 402 drives:

| Product | Profile as documented | Section |
|---|---|---|
| EL7201/7211/7221 servo terminals | MDP742 by default; DS402 after an ESI update | EL72x1 |
| AX8000 multi-axis servo (AX8108, AX8118, AX8206 …) | CiA 402 objects, cyclic modes only | AX8000 |
| EL7037/EL7047 stepper terminals | not CiA 402: Beckhoff's own stepper objects | EL70x7 |
| AX1000 servo, AF1000 frequency inverter | no object documentation published | AX1000 and AF1000 |

All pages are in the Beckhoff Information System,
`https://infosys.beckhoff.com/content/1033/<set>/<page>`. Page numbers are given in brackets.

## EL72x1 servo terminals (EL7201, EL7211, EL7221)

**Read 2026-10-26**:

- EL72x1-901x documentation v2.4.0 (2024-10-07), covering EL7201/7211/7221-9014/-9015 (set
  `el72x1-901x`)
- EL72x1-001x v3.0.0 (2024-10-02), covering EL7201/7211-0010/-0011. The pages cited below have
  the same numbers and the same text in both sets.

The -0000/-0001 family uses other pages and was not checked.

### Two profiles, and the terminal ships with the wrong one for a CiA 402 master

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

### In DS402 (-0011, -9015)

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

### The field case

In ICube `ethercat_driver_ros2` issue #163 (closed 2025-03-28, read 2026-10-26,
https://github.com/ICube-Robotics/ethercat_driver_ros2/issues/163), an EL7221-9015 in DS402 sent
statusword 104 (0x0068): fault together with switch on disabled. The driver's strict-mask decoder
rejected it. The reporter made the decoder read fault-first and the axis ran; no root cause was
found. Read such a word as Fault (`../state-machine.md`). With bit 5 reserved on this terminal,
only bits 3 and 6 carry meaning in it.

## AX8000 axis modules (AX8108, AX8118, AX8206 …)

**Read 2026-11-08**: object dictionary "AX8xxx | Axis module of AX8000 system" v1.7.0
(`ax8xxx_objects`), functional description v2.1.0 (`ax8000_fb`), diagnostic messages v1.7.0
(`ax8xxx_diags`) and operating instructions v2.4.0 (`ax8000_ba`). None of the pages shows a date.
An older set `ax8xxx_object` (singular) still turns up in searches; its pages return 404.

- **Standard CiA 402 objects, no MDP742.** 0x6040, 0x6041, 0x6060, 0x605A, 0x605E, 0x603F,
  touch probe and 0x6502 are in the dictionary under their profile indices [18797721227]. No
  0x7010/0x6010 drive objects were found and nothing mentions a second profile. Vendor objects
  sit in slots from 0x3000 up [18797825035].
- **Second channel.** On a two-channel AX82xx the profile objects of channel B are at +0x800
  (0x6860, 0x6871 …), the profile's own axis offset, but the vendor slot objects at +0x400
  [10524952459].
- **Cyclic modes only.** 0x6060 takes 8, 9, 10, 11 (CSTCA) and 15 (CSPAF), plus the vendor
  values −1 (preliminary CSPAF), −9 (CSV "remote") and −10 (CST "remote"). It defaults to 0,
  so write it at start-up [18797964299]. 0x6502 is 0x780, bits 7–10 [18798076939]. No PP, PV or
  homing mode, and no 0x6098 was found: the master homes. 0x60C0 offers 0 (linear) and −2
  (cubic) [18798117259].
- **Quick stop exists.** 0x605A takes 2 (default: ramp, then Switch on disabled), 6 (ramp and
  stay in Quick stop active) and −1 (quick stop disabled) [18797960203]. With the default 2
  there is no way back by T16; set 6 if the master relies on it. 0x6085 defaults to 360000 in the
  units set by 0x3005 [18798337547].
- **0x605E**: 2 closed-loop ramp (default), 0 torque off, and the vendor values −1 "NC handling"
  and −2 shorted coils or DC braking [18797962251]. A fast-stop input with its own reaction is
  configured in 0x300E [18797896971].
- **No 0x605B or 0x605D.** The axis module's object list goes from 0x605A to 0x605E
  [18797721227]. Controlword bit 8 is labelled halt, but no page says what it does in the cyclic
  modes [18797956107].
- **A delay after Operation enabled.** On reaching Operation enabled the drive waits the drive-on
  delay 0x3000:03 (default 100 ms, up to 5 s) for the brake to open, and ignores set-points until
  it ends. Torque stays on for the drive-off delay 0x3000:04 (default 150 ms) after enable is
  removed [18797735179, 18797736715, 9842278411]. Wait for statusword bit 12 before commanding
  motion, not only for Operation enabled; that bit 12 is the better signal is our reading.
  Whether 0x000F in Ready to switch on goes straight to Operation enabled is not stated.
- **Statusword bits 10, 12 and 13.** The dictionary names bit 10 a status toggle, bit 12 "drive
  follows the command value" and bit 13 an input cycle counter, all tied to 0x60D9/0x60DA
  (ETG.6010 functions). Controlword bits 5–6 are an output cycle counter [18797956107,
  18797958155]. Do not read bit 10 as target reached. 0x60DA defaults to 0 [18798044171]; that
  the toggle and counters stay off until 0x60DA enables them is our reading, as on the EL72x1.
- **0x603F holds the text ID of the last error diagnosis message** [18797954059]. Look the
  number up in the diagnostic message list; it is not one of the profile's error codes
  (`../errors.md`). Some errors clear with controlword bit 7 only when 0x3004:04 "extended fault
  reset" is set [18797801739].
- **Units come from 0x3005.** Position defaults to 2^20 counts per 360° and can be set to other
  binary resolutions or to metric units [18797826827]. Velocity defaults to 0.0001 rpm (or
  0.1 µm/s), 0x3005:02 [18797828363], and torque scaling to 1 N·m (or 1 N), 0x3005:05
  [18797832971]. 0x6071 is in thousandths of the motor
  **standstill** torque 0x6076, not of rated torque [18798482699].
- **PDO mapping per module.** The dictionary is split into modules (axis, interpolator, position,
  velocity and torque control, filters, encoders), each with its own 0x16xx/0x1Axx mapping
  objects, writable in Pre-operational [18797721227, 18797722123]. The default assignment is
  0x1600, 0x1620 and 0x1623 in 0x1C12, and 0x1A20 and 0x1A26 in 0x1C13 [18797167243,
  18797190795]; what they contain is not on the pages read, so read the mapping from the drive.
  Each module also has "dynamic" mapping objects (0x16E0/0x1AE0, assigned in 0x1C14/0x1C15,
  empty by default) that stay writable in every state; their purpose is not described
  [18797724171, 18797241995].
- **Cycle**: 62.5 µs minimum, with distributed clocks [7917947019]. Diagnosis messages reject a
  Sync0 other than one fixed value and a Sync1 that is not a multiple of Sync0 [18793851531,
  11591665931]. Free run was not found.
- **Firmware**: the ESI revision matches the firmware (revision -0107 = V1.07, which needs
  bootloader 2.0.0 or later) [18381895307].

## EL70x7 stepper terminals (EL7037, EL7047)

**Read 2026-11-08**: "EL70x7 | EtherCAT Terminals, 1-channel motion interface, stepper motor,
vector control, with incremental encoder", v2.3.0 (2026-07-09), set `el70x7`. The pages read do
not separate EL7037 from EL7047. The EL7041 has its own documentation, not read.

**This terminal is not a CiA 402 drive.** Code or a master built for one does not port to it;
plan it as a separate interface.

- **Beckhoff's own objects.** Stepper outputs 0x7010, encoder 0x7000 and positioning 0x7020,
  with inputs at 0x6010, 0x6000 and 0x6020 [1305112715]. No 0x6040/0x6041, no 0x6060 and no
  0x605A were found on the object and PDO pages [11698853515, 11698807179, 11698650507].
  0x7010/0x6010 are the same indices as MDP742 on the EL72x1, with a different meaning.
- **No state machine.** 0x7010:01 enables the output stage, and 0x6010:01/:02 report ready to
  enable and ready [11698853515, 11698807179]. A rising edge on 0x7010:02 clears all errors;
  warning and error bits are 0x6010:03/:04, with the detail in 0xA010.
- **Modes** in 0x8012:01: 0 automatic (default), 1 velocity direct, 3 position controller,
  4 and 5 extended velocity and position, 6 sensorless velocity [11698650507]. Automatic picks
  1 or 3 from the predefined PDO assignment chosen [1305123211]. The position controller, fed
  cyclically through 0x7010:11, is the closest to CSP, but Beckhoff does not call it that. The
  extended modes need Beckhoff AS10xx motors [1305129355].
- **Velocity is a fraction, not a unit.** ±32767 in 0x7010:21 is ±100 % of the speed range set
  in 0x8012:05: 1000 to 32000 full steps/s, default 2000 [11698650507]. Position on the internal
  counter is 64 microsteps per full step, 12800 per revolution of a 200-step motor
  [1305126283].
- **Homing and stopping live in the positioning interface (0x7020/0x6020).** Homing is a
  "calibration" start type on a cam, optionally with the encoder C track; Beckhoff warns that the
  cam inputs are polled, so the homed position carries an error [11686582923]. An emergency stop
  is a rising edge on 0x7020:02 with its own deceleration [11698853515]. There is no quick stop
  object.
- **Step loss** shows as a stall bit, 0x6010:08, and becomes an error only when 0x8012:0A is set
  [11698807179, 11698650507].
- **PDOs**: predefined assignments for velocity control, position control and the positioning
  interface, selected in 0x1C12/0x1C13 [1305112715]. Cycle-time limits were not found.

## AX1000 and AF1000

**Read 2026-11-08**: "AX1000 | Economy servo drives – Operating instructions" v1.0.0
(`ax1000_ba`) and the AF1000 operating instructions v1.1.0 (`af1000_ba`), neither dated.

Both documents describe hardware only: wiring, technical data, LEDs, safety options and a
commissioning checklist. **Beckhoff publishes no object dictionary or functional description for
either** on Infosys; the AX1000 documentation index names the operating instructions as its only
document [driveinfosys 22969299851]. The AX8000 has both.

- **AX1000.** Beckhoff's product page states "CiA402 according to IEC 61800-7-201 (CoE)"
  (beckhoff.com, AX1106-3201-0000, read 2026-11-08). Which modes, objects and PDOs it has is not
  documented. Do not assume it matches the AX8000. Some types were still marked "product
  announcement" on that date.
- **AF1000.** No profile is named anywhere read: not CiA 402, not velocity mode (vl), not MDP742.
  It runs asynchronous, synchronous and reluctance motors without feedback [af1000_ba
  17956678539].
- For either drive, read the objects from the ESI (`ethercat-esi`) or upload the dictionary from
  a drive before writing a master for it.
