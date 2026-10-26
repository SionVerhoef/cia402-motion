# maxon EPOS4

**Read 2026-10-26**: EPOS4 Firmware Specification, Edition 2026-07 (DocID rel13740),
https://www.maxongroup.com/medias/sys_master/root/9579215585310/EPOS4-Firmware-Specification-En.pdf,
the edition linked from maxon's EPOS4 product page that day. Sections and pages are given in
brackets. Some items are firmware-dependent, and the firmware is named where it matters.

## Modes and the state machine

- **Modes: PP, PV, HM, CSP, CSV, CST.** 0x6502 = 0x000003A5. There is no IP, PT or VL and no
  manufacturer mode [§6.2.151]. 0x6060 is stored and defaults to 1 (PP) [§6.2.101].
- **0x000F in Ready to switch on is "Switch on & Enable operation"** (T3 and T4). The drive goes
  on to Operation enabled by itself [§2.2.3, table 2-7].
- **Statusword bit 9 (remote) shows NMT Operational**, not local/remote control. Bit 15 is set
  when homing is attained and cleared on a position-counter overflow or a sensor error. Bits 8 and
  14 read 0 [§6.2.95].
- **A standstill window (0x30E0) holds** the transitions out of Operation enabled, and Fault
  reaction active → Fault, until the axis is at standstill [§6.2.73].

## Option codes

| Object | EPOS4 allows | Default |
|---|---|---|
| 0x605A quick stop | **6 only** (quick-stop ramp, stay in Quick stop active) | 6 |
| 0x605B shutdown | 0, 1 | 0 |
| 0x605C disable operation | 0, 1 | 1 |
| 0x605D halt | 1, 2 (from firmware 0x0180, 2025-05) | 1 |
| 0x605E fault reaction | 0, 1, 2 | 2 |
| 0x6007 abort connection | 2, 3 | 3 |

[§6.2.92, §6.2.96–6.2.100, version history §8.2]. With 0x605A = 6, an EPOS4 always stays in
Quick stop active after a quick stop, so T16 (0x000F) brings it back. Code written for an EPOS4
that relies on that breaks on drives with 0x605A = 0–4.

## Homing

- **Methods: 1, 2, 7, 11, 17, 18, 23, 27, 33, 34, 37 and −1 to −4.** 0x60E3 lists them. **35 is
  not supported; use 37** [§3.5.3, §6.2.125, §6.2.143].
- **−1 to −4 are current-threshold (hard stop) homing**: the end stop is detected when the
  averaged current exceeds 0x30B2. −1 positive with index, −2 negative with index, −3 positive,
  −4 negative [§3.5.3, methods −1 to −4]. Other vendors use −1 for the *negative* direction:
  `../homing.md`.
- **37 with the power stage disabled takes effect at once.** With operation enabled, the axis
  first moves the home-offset move distance 0x30B1 [§3.5.3, method 37].
- **The home offset is 0x30B0 "home position"**, with 0x30B1 for the move after homing. 0x607C
  exists only from firmware 0x0180 (2025-05), as a mirror of 0x30B0 [§6.2.116, §8.2].
- **Touch probe 1 only.** It cannot run during homing, and homing clears its latches
  [§6.2.134].

## Units and monitoring

- **No factor group.** 0x608F, 0x6091, 0x6092 and 0x6096 are absent. Units come from 0x60A8
  (position: increments, the only legal value), 0x60A9 (velocity: rpm with a prefix, deci down to
  micro) and 0x60AA (acceleration: rpm/s), writable only with the power stage disabled. Gearing is
  the manufacturer object 0x3003 [§2.3, §6.2.128–6.2.130, §6.2.55].
- **0x6066 following-error timeout is fixed at 0.** Writing 0x6065 = 4,294,967,295 switches
  following-error monitoring off [§6.2.105, §6.2.106].
- **0x6067 position window defaults to 4,294,967,295 (off).** Target reached is then set at the
  end of the trajectory, wherever the axis actually is. The window exists from firmware 0x0170
  [§6.2.107].

## Profile position

Controlword bits 9 and 10 are reserved in every mode, so there is no change-on-set-point. Bit 15
in PP is maxon's "endless movement" [§6.2.94].
