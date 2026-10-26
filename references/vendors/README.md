# Vendor deviations

The profile leaves a lot to the manufacturer, and every vendor document read for this skill
departs from it somewhere that matters in commissioning. These pages hold **deviations only**:
what a drive does differently from `../state-machine.md`, `../modes.md` and the other
profile pages, and what it adds or leaves out.

| Page | Products |
|---|---|
| `beckhoff.md` | EL7201, EL7211, EL7221 servo terminals: MDP742 vs DS402 |
| `hiwin.md` | D-series EtherCAT drives (2014 guide) |
| `lenze.md` | i550 / i650 motec, i750 / i950 |
| `linmot.md` | C1250-MI, C1251-MI with the CiA 402 interface |
| `maxon.md` | EPOS4 |
| `nanotec.md` | CL3-E, NP5 |
| `omron.md` | 1S series (R88D-1SN…-ECT) |
| `synapticon.md` | SOMANET, firmware v5 |

## How to use these pages

- **Every claim names its document, version and the date it was read.** Firmware moves on. A
  page says what that document said on that date, not what the drive on the machine does today.
  For a decision that matters, check the manual for the firmware actually installed. Use
  **ethercat-esi**, or the drive's ESI/EDS file, for its objects and value ranges.
- **Quote the vendor and the source when you use a claim.** Never present it as the profile, and
  never assume another vendor does the same.
- **A drive not listed here is not "standard".** No page means nothing was read, not that there
  are no deviations. Say so, and work from the profile and the drive's own manual.

## Porting between drives: where they differ

As read 2026-10-26. "not read" means the documents read did not cover it.

| | 0x605A quick stop | Homing −1 | 35 / 37 | Scaling | PDO mapping | Modes (0x6060) |
|---|---|---|---|---|---|---|
| Beckhoff EL72x1, DS402 | absent; CW bit 2 reserved | no homing mode | no homing mode | raw increments, UINT32 positions | fixed, one object per PDO; choose via 0x1C12/0x1C13 | 8, 9, 10, 11 |
| HIWIN D-series (2014) | not read | none (1–6, 33, 34 only) | neither | not read | not read | not read |
| Lenze i750 / i950 | not read | not read | not read | not read | free; default set has 0x60B1, 0x60E0/0x60E1 | CSP, CST, CSV, velocity (examples) |
| maxon EPOS4 | 6 only | hard stop, positive, index | 37 only | no factor group; 0x60A8–0x60AA, gear 0x3003 | not read | 1, 3, 6, 8, 9, 10 |
| Nanotec CL3-E / NP5 | 0, 1, 2 | block, negative, index | 35 (CL3-E) | not read | not read | not read; adds −1, −2 |
| Omron 1S | not read | not read | not read | 0x6091 (≥ 250 µs cycle), no 0x6092 | fixed 0x17xx/0x1Bxx + editable 0x1600/0x1A00 | not read |
| Synapticon v5 | 0, 2, 6 | end stop, negative, index | both | 0x6091 is motor-to-encoder shaft | not read | 1, 3, 4, 6, 8, 9, 10 + −1 to −6 |
| LinMot C125x-MI | absent | only −128 to −111 | not supported | vendor parameters (0x60FF in 1 µm/s) | predefined modules + free 0x1620/0x1A20 | 1, 6, 8, 10 + 0x8A |

The cell that bites most often is the quick-stop column. Code written on an EPOS4, where 0x605A
is always 6, relies on 0x000F returning from Quick stop active (T16). On a Nanotec, a Synapticon
set to 2, or a Beckhoff terminal, that path does not exist.

## What a generic master had to allow for: CODESYS

Read 2026-10-26: CODESYS SoftMotion, "Configuration of the Generic CiA402 Axis" (no version or
date on the page),
https://content.helpme-codesys.com/en/CODESYS%20SoftMotion/_sm_drives_generic_cia402_axis.html.

A master that drives any vendor's CiA 402 drive ends up with switches for the ways drives
disagree. That makes this list a map of where to expect trouble, whatever the master:

- **Statusword bit 12 is not set by every drive.** `MC_Power.Status` needs bits 0, 1, 2, 5 and
  12. `_bCheckBit12InPositionMode` = FALSE drops the bit-12 check in CSP and IP.
- **Homing completion bits come in different orders.** `_bCheckBit10PostHoming` (done on bits 10
  and 12, as the profile says, or on bit 12 alone), `_bPreHomingWaitBit12Clear` (wait for bit 12
  to clear before raising bit 4), `_uiHomingWaitListeningBits101213` (ignore bits 10/12/13 for
  some cycles after bit 4, for drives slow to clear them), and `_bCheckBit13InHomingMode`.
- **Some drives want controlword bit 4 set in CSP**, which the profile reserves:
  `_bSetControlBit4InCSP`.
- **The mode must be confirmed**: `_bCheckOpMode` checks 0x6061 against 0x6060 before enabling.
- **Multi-axis**: for CANopen EDS files the page gives the per-axis object range as 67FFh +
  X × 800h. For EtherCAT the number of axes comes from the ESI (its DS402 channel count), so
  ask **ethercat-esi**.

Kollmorgen AKD has no page: its manuals could not be downloaded on 2026-10-26.

## Adding a vendor

Read the vendor's own manual or knowledge-base article. Write each deviation in your own words,
with the document title, version, URL, section or page and the date read. Copy no passages,
tables or figures (see the repository's `CLAUDE.md`). Name products, never customers or
machines.
