# Vendor deviations

The profile leaves a lot to the manufacturer, and every vendor document read for this skill
departs from it somewhere that matters in commissioning. These pages hold **deviations only**:
what a drive does differently from `../state-machine.md`, `../modes.md` and the other
profile pages, and what it adds or leaves out.

| Page | Products |
|---|---|
| `beckhoff.md` | EL7201, EL7211, EL7221 servo terminals: MDP742 vs DS402 |
| `festo.md` | CMMT-AS (S1, S3), CMMT-ST, firmware V37.1 |
| `hiwin.md` | D-series EtherCAT drives (2014 guide) |
| `lenze.md` | i550 / i650 motec, i750 / i950 |
| `linmot.md` | C1250-MI, C1251-MI with the CiA 402 interface |
| `maxon.md` | EPOS4 |
| `nanotec.md` | CL3-E, NP5 |
| `nidec.md` | Control Techniques SI-EtherCAT module on Unidrive M and Digitax HD; Digitax HD M753 (built-in) |
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

Two tables, one row per vendor page. Cells are short; the vendor page has the details and the
source. Read 2026-10-26 (Nidec and Festo 2026-11-08); tables last updated 2026-11-08. "not read" means the
documents read did not cover it; "absent" means the object is not in the drive's dictionary.

### Stopping and the state machine

| | 0x605A quick stop | 0x605B = 0 does | 0x605D default | 0x000F from Ready to switch on | Drive-side delay |
|---|---|---|---|---|---|
| Beckhoff EL72x1, DS402 | absent; CW bit 2 reserved | not read | not read | not read | not read |
| Festo CMMT | absent; ramps on 0x6085, end state not documented | absent; enable off = cat. 1 stop | absent; halt ignored in CSx | Operation enabled (T3 + T4) | not read |
| HIWIN D-series (2014) | not read | not read | not read | not read | not read |
| Lenze i750 / i950 | not read | not read | not read | not read | not read |
| LinMot C125x-MI | absent | absent | absent | not read | not read |
| maxon EPOS4 | 6 only | coast, also on T9 | 1 | Operation enabled (T3 + T4) | waits for standstill (0x30E0) |
| Nanotec CL3-E / NP5 | 0, 1, 2 | not read | not read | not read | not read |
| Nidec SI-EtherCAT | 0, 1, 2, 5, 6; default 2 | ramp, then disable | 0: halt does nothing | Operation enabled (T3 + T4) | 40 ms background loop |
| Omron 1S | not read | not read | not read | not read | not read |
| Synapticon v5 | 0, 2, 6 | absent | absent | Operation enabled (T3 + T4) | not read |

The cell that bites most often is the quick-stop column. Code written on an EPOS4, where 0x605A
is always 6, relies on 0x000F returning from Quick stop active (T16). On a Nanotec, a Synapticon
set to 2, or a Beckhoff terminal, that path does not exist. Next come 0x605B = 0, which coasts on
most drives but ramps on a Nidec, and halt, which does nothing on a Nidec until 0x605D is set. A
drive that takes 0x000F in Ready to switch on as T3 + T4 can go straight to Operation enabled,
so a master that sends 0x000F there and waits to see Switched on may never see it. Sending
0x0007, waiting for Switched on, then 0x000F works on every drive in the table.

### Motion

| | Homing −1 | 35 / 37 | Velocity unit | Scaling | PDO mapping | Modes (0x6060) |
|---|---|---|---|---|---|---|
| Beckhoff EL72x1, DS402 | no homing mode | no homing mode | 0x6090 = 1 rev/s | raw increments, UINT32 | fixed, one object each | 8, 9, 10, 11 |
| Festo CMMT | fixed stop, negative, index | 37 only | rpm (factory) | 0x60A8–0x60AB, powers of 10; no 0x6091/0x6092 | free 0x1600/0x1A00, 16 each | 0, 1, 3, 4, 6, 8, 9, 10, −3, −20 |
| HIWIN D-series (2014) | none (1–6, 33, 34) | neither | not read | not read | not read | not read |
| Lenze i750 / i950 | not read | not read | not read | not read | free; default maps 0x60E0/0x60E1 | CSP, CST, CSV, vl (examples) |
| LinMot C125x-MI | vendor −128 to −111 | not supported | 1 µm/s | vendor parameters | modules + free 0x1620/0x1A20 | 1, 6, 8, 10, 0x8A |
| maxon EPOS4 | hard stop, positive, index | 37 only | rpm with prefix (0x60A9) | no factor group | not read | 1, 3, 6, 8, 9, 10 |
| Nanotec CL3-E / NP5 | block, negative, index | 35 (CL3-E) | rpm (factory) | not read | not read | not read; adds −1, −2 |
| Nidec SI-EtherCAT | none (0x6098 unsigned) | both (35 legacy) | units per **ms** | 0x6091/0x6092 taken at T3 | one PDO per SM; default vl | 1, 2, 6–10, by host |
| Omron 1S | not read | not read | not read | 0x6091 (≥ 250 µs), no 0x6092 | fixed + editable 0x1600/0x1A00 | not read |
| Synapticon v5 | end stop, negative, index | both | rpm (default) | 0x6091 is motor-to-encoder | not read | 1, 3, 4, 6, 8, 9, 10, −1 to −6 |

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
