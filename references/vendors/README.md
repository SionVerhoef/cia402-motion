# Vendor deviations

The profile leaves a lot to the manufacturer, and every vendor document read for this skill
departs from it somewhere that matters in commissioning. These pages hold **deviations only**:
what a drive does differently from `../state-machine.md`, `../modes.md` and the other
profile pages, and what it adds or leaves out.

| Page | Products |
|---|---|
| `beckhoff.md` | EL7201/7211/7221 servo terminals (MDP742 vs DS402); AX8000; EL7037/EL7047 steppers (not CiA 402); AX1000, AF1000 (no object documentation) |
| `delta.md` | ASDA-A3-EP (400 V, EtherCAT); the 230 V ASDA-A3-E was not read |
| `festo.md` | CMMT-AS (S1, S3), CMMT-ST, firmware V37.1 |
| `hiwin.md` | D-series EtherCAT drives (2014 guide) |
| `keb.md` | COMBIVERT F6 / S6 (Compact, Application, Pro control boards), software V3.0 |
| `leadshine.md` | EL8-EC AC servo drives; EM3E-522E/556E/870E EtherCAT stepper drives |
| `lenze.md` | i550 / i650 motec, i700, i750, i950 (with the "CiA 402 advanced" application) |
| `linmot.md` | C1250-MI, C1251-MI with the CiA 402 interface |
| `maxon.md` | EPOS4 |
| `mitsubishi.md` | MR-J4-_TM_ with the ABCC-M40-ECT EtherCAT module (software A0–B4) |
| `nanotec.md` | CL3-E, NP5 |
| `nidec.md` | Control Techniques SI-EtherCAT module on Unidrive M and Digitax HD; Digitax HD M753 (built-in) |
| `omron.md` | 1S series (R88D-1SN…-ECT) |
| `rexroth.md` | ctrlX DRIVE, firmware AXS-V-06RS (not IndraDrive / HCS01) |
| `sew.md` | MOVI-C with the CiA402 device profile: MOVIDRIVE modular/system/technology, MOVITRAC advanced, decentralized units |
| `stober.md` | SC6, SI6 with the "CiA 402" or "CiA 402 HiRes Motion" application, firmware V 6.4-D or later |
| `synapticon.md` | SOMANET, firmware v5 |
| `yaskawa.md` | Σ-V SGDV-E1 / SGDV-E5 with the SGDV-OCA01A EtherCAT module (2010 manual; not Σ-7) |

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
source. Read 2026-10-26 (Nidec, Festo, Rexroth, SEW, STOBER, Yaskawa, Mitsubishi, Delta, Leadshine, KEB, the Lenze manuals and Beckhoff AX8000 2026-11-08); tables last updated 2026-11-08. "not read" means the
documents read did not cover it; "absent" means the object is not in the drive's dictionary.

### Stopping and the state machine

| | 0x605A quick stop | 0x605B = 0 does | 0x605D default | 0x000F from Ready to switch on | Drive-side delay |
|---|---|---|---|---|---|
| Beckhoff EL72x1, DS402 | absent; CW bit 2 reserved | not read | not read | not read | not read |
| Beckhoff AX8000 | 2, 6, −1; default 2 | absent | absent | not stated | drive-on delay 0x3000:03, 100 ms |
| Delta ASDA-A3-EP | absent; CW bit 2 ramps on 0x6085, limit switches on the P5.003 time | 0 = coast (no dynamic brake), −1 = dynamic brake | absent | Operation enabled (T3 + T4) | not read |
| Festo CMMT | absent; ramps on 0x6085, end state not documented | absent; enable off = cat. 1 stop | absent; halt ignored in CSx | Operation enabled (T3 + T4) | not read |
| HIWIN D-series (2014) | not read | not read | not read | not read | not read |
| KEB F6 / S6 (V3.0) | 0, −1 to −6 (no 1–8); off unless co32 bit 9; 0, −3, −5 end in Switched on | power off; −1 / 1 = ramp | not mentioned; halt in VL, HM, PP only | not stated | mod-off pause / protection time; brake wait (co21 bit 5) |
| Leadshine EL8-EC / EM3E | 0–3, 5–7 (EM3E also 4); default 2 (EL8), 6 (EM3E); EM3E: an alarm unless 0x22B4 = 1 | EL8: stop by P05.06 (default braking, not coast); EM3E not listed | 1; EL8 halt in CSx unclear | setting: 0x5004:0F bit 2 (EL8 default off) | EM3E brake delays 0x4003 (250 ms each) |
| Lenze i700 / i750 / i950 | 2, 6; default 2 | torque off (default); 1 = ramp first; absent on i700 | absent; halt ramps to 0 | not stated | waits brake closing time (0x2820:002) |
| LinMot C125x-MI | absent | absent | absent | not read | not read |
| maxon EPOS4 | 6 only | coast, also on T9 | 1 | Operation enabled (T3 + T4) | waits for standstill (0x30E0) |
| Mitsubishi MR-J4-TM | 2 only; dynamic brake in cst/tq | absent (0x605C, 0x605E too) | 1 only; halt ignored in CSx | Operation enabled (also from Switch on disabled) | homing status up to 50 ms late; hold fault reset 10 ms |
| Nanotec CL3-E / NP5 | 0, 1, 2 | not read | not read | not read | not read |
| Nidec SI-EtherCAT | 0, 1, 2, 5, 6; default 2 | ramp, then disable | 0: halt does nothing | Operation enabled (T3 + T4) | 40 ms background loop |
| Omron 1S | not read | not read | not read | not read | not read |
| Rexroth ctrlX DRIVE | 0, 2, 3, 6, 7 | torque off; default is −1 (use 0x605C) | not stated; halt ignored in CSx | not stated | magnetising / brake release; Shutdown only in OM |
| SEW MOVI-C (CiA402) | 2, 6; default not stated | absent (0x605C too) | 1 only (listed default 0) | not stated | brake delay at a fault, whatever 0x605E says |
| STOBER SC6 / SI6 | present (A536), values not given; always ends in Switch on disabled | absent | absent | not stated | hardware enable (A60) gates T2–T6 and T8 |
| Synapticon v5 | 0, 2, 6 | absent | absent | Operation enabled (T3 + T4) | not read |
| Yaskawa Σ-V SGDV-OCA01A | 0–3 (4 undocumented), default 2; all end in Switch on disabled | power stage off (default); 1 = ramp; torque modes always off | 1 (ramp, 0x6084) | Operation enabled (T3 + T4) | Ready to switch on waits for main power and EtherCAT OP |

The cell that bites most often is the quick-stop column. Code written on an EPOS4, where 0x605A is
always 6, relies on 0x000F returning from Quick stop active (T16). On a Nanotec, a Synapticon set to
2, a Lenze or a Beckhoff AX8000 at its default (2), or a Beckhoff terminal, that path does not
exist. Next come 0x605B = 0, which coasts on most drives but ramps on a Nidec, and halt, which does
nothing on a Nidec until 0x605D is set. A drive that takes 0x000F in Ready to switch on as T3 + T4
can go straight to Operation enabled, so a master that sends 0x000F there and waits to see Switched
on may never see it. Sending 0x0007, waiting for Switched on, then 0x000F works on every drive in
the table.

### Motion

| | Homing −1 | 35 / 37 | Velocity unit | Scaling | PDO mapping | Modes (0x6060) |
|---|---|---|---|---|---|---|
| Beckhoff EL72x1, DS402 | no homing mode | no homing mode | 0x6090 = 1 rev/s | raw increments, UINT32 | fixed, one object each | 8, 9, 10, 11 |
| Beckhoff AX8000 | no homing mode | no homing mode | 0.0001 rpm (0x3005:02) | 0x3005; default 2^20 per rev | per module, writable in PreOp | 8–11, 15; vendor −1, −9, −10 |
| Delta ASDA-A3-EP | hard stop + index (direction only in a figure) | 35 only (0x6098 range −4 to 35) | 0.1 rpm; 0x6081 in PUU/s; ramps are ms to 3000 rpm | 0x6093 = E-gear on 2²⁴ pulses/rev; no 0x608F/0x6091/0x6092 | 4 + 4 maps of 8, one of each assigned; default without 0x6060 | 1, 3, 4, 6, 8, 9, 10 |
| Festo CMMT | fixed stop, negative, index | 37 only | rpm (factory) | 0x60A8–0x60AB, powers of 10; no 0x6091/0x6092 | free 0x1600/0x1A00, 16 each | 0, 1, 3, 4, 6, 8, 9, 10, −3, −20 |
| HIWIN D-series (2014) | none (1–6, 33, 34) | neither | not read | not read | not read | not read |
| KEB F6 / S6 (V3.0) | none described | 37 (35 alias), default 37 | rpm / 2ⁿ (co02) | co03 bits/rev (default 16); no 0x6091/0x6092 described | not read (separate fieldbus manual) | 1, 2, 6, 8, 9, 10, −2 (jog); 0x6502 omits 10 |
| Leadshine EL8-EC / EM3E | EL8: torque end stop, positive, + index; EM3E none | both (EM3E: 37 preferred) | EL8 command units/s; EM3E pulses/s | EL8: own 0x6091/0x6092 rule, P00.08 overrides, 10000/rev default; EM3E: microsteps 0x2001 | 0x1600–03 / 0x1A00–01, 8 objects each; EL8 default CSP + probe | EL8 1, 3, 4, 6, 8, 9, 10; EM3E 1, 3, 6, 8 |
| Lenze i700 / i750 / i950 | none; i950 "advanced": torque end stop, negative | none; "advanced" uses 0 | n-unit: 2³¹ = 480000 rpm | 0x608F, 2¹⁶–2³⁰ inc/rev; no 0x6091/0x6092 | fixed PDO per mode, plus free (i700: 8 objects); default maps 0x60E0/0x60E1 | 2, 8, 9, 10; "advanced" adds 6 |
| LinMot C125x-MI | vendor −128 to −111 | not supported | 1 µm/s | vendor parameters | modules + free 0x1620/0x1A20 | 1, 6, 8, 10, 0x8A |
| maxon EPOS4 | hard stop, positive, index | 37 only | rpm with prefix (0x60A9) | no factor group | not read | 1, 3, 6, 8, 9, 10 |
| Mitsubishi MR-J4-TM | dog, rear end, then Z, positive (−33 reversed) | both, also with servo off | 0.01 rpm, fixed; ramps are times in ms | 0x6091 = electronic gear; 0x608F/0x6092 read-only; CSx in pulses only | one of 0x1600–03 / 0x1A00–03, 32 objects / 64 bytes | 1, 3, 4, 6, 8, 9, 10, −100, −101, −103 (limited by Pr. PA01) |
| Nanotec CL3-E / NP5 | block, negative, index | 35 (CL3-E) | rpm (factory) | not read | not read | not read; adds −1, −2 |
| Nidec SI-EtherCAT | none (0x6098 unsigned) | both (35 legacy) | units per **ms** | 0x6091/0x6092 taken at T3 | one PDO per SM; default vl | 1, 2, 6–10, by host |
| Omron 1S | not read | not read | not read | 0x6091 (≥ 250 µs), no 0x6092 | fixed + editable 0x1600/0x1A00 | not read |
| Rexroth ctrlX DRIVE | free configuration (0x2500:02) | 37 only | preset 0.0001 rpm or 0.001 mm/min | own (0x2900–0x2906), CM only; no 0x6092 | free, 20 objects / 50 bytes | 1, 3, 4, 6, 8, 9, 10, −1 (one vendor mode) |
| SEW MOVI-C (CiA402) | none | 37 only | inc/s (2023 manual); 2018 manual says 0.0001 rpm | none: fixed 65536 inc/rev, scale in the master | slot modules (csp, csv, pp/pv default) + up to 8 × 32 bit | 1, 3, 6, 8, 9, 10; −13 to −25 are SEW drive functions |
| STOBER SC6 / SI6 | torque/force limit, positive, no index | 37 (35 described as the same) | not stated; decimals in A310/A311 | 0x6091/0x6092, 2²⁰ inc/rev default; no 0x608F | free, 24 objects per axis; re-export the DS6 ESI | 1, 3, 4, 6, 7, 8, 9, 10, −1 (jog) |
| Synapticon v5 | end stop, negative, index | both | rpm (default) | 0x6091 is motor-to-encoder | not read | 1, 3, 4, 6, 8, 9, 10, −1 to −6 |
| Yaskawa Σ-V SGDV-OCA01A | none (0x6098 is 0–35) | 35 only (default, not stored) | inc/s × 0x2702 ratio (default 1) | own 0x2701–0x2703, applied at 0x2700 or power cycle; no factor group | 4 + 4 maps of 8, 2 per SM; default CSP pair, no 0x6060 | 1, 3, 4, 6, 7, 8, 9, 10 |

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

The Beckhoff EL70x7 steppers are not CiA 402 drives and have no row; the AX1000 and AF1000 have
no published object documentation (`beckhoff.md`).

Kollmorgen AKD has no page: its manuals could not be downloaded on 2026-10-26.

## Adding a vendor

Read the vendor's own manual or knowledge-base article. Write each deviation in your own words,
with the document title, version, URL, section or page and the date read. Copy no passages,
tables or figures (see the repository's `CLAUDE.md`). Name products, never customers or
machines.
