# Delta ASDA-A3-EP (EtherCAT, CoE)

**Read 2026-11-08**: Delta Electronics, *Delta ASDA-A3-EP Servo Drive User Manual*,
DELTA_IA-ASD_ASDA-A3-EP_UM_EN_20241018, V1.0, first edition (October 2024). Delta publishes
its manuals and ESI files in the Download Center at https://www.deltaww.com. Page numbers in
brackets are PDF pages, not the manual's own chapter-page numbers (PDF p. 362 is the manual's
10-1).

The manual covers the **ASD-A3-xx43-EP**: 400 V three-phase, 400 W to 15 kW, with EtherCAT,
STO and full-closed loop [p. 22]. It gives no firmware version for the CoE functions; the only
version named is v1.0105 or later, needed for the optional ACS3-SF safety module [p. 560].
**The 230 V ASDA-A3-E has its own manual, which was not read.** Do not assume the A3-E
matches this page without checking.

## Before anything works

- **P1.001 must be 0x0C (EtherCAT mode).** That is the default [p. 237], and ASDA-Soft's
  EtherCAT diagnosis checks it first [p. 451].
- **The station alias comes from the ESC EEPROM by default.** P3.018.A = 1 takes it from
  P3.000 instead [pp. 289, 368].
- **Ring topology needs P3.018.Z = 2**, which turns off the AL185 disconnection check
  [p. 368].
- **The drive watches PDOs itself** (P3.022). AL180 fires after a set time without a PDO, in
  every mode (default 255 ms). AL3E3 fires after a set number of missed cycles in CSP, CSV and
  CST (default 4) [pp. 369, 293].
- **SYNC0 cycle: 125, 250 or 500 µs, or 1 to 10 ms in whole ms** [p. 373]. 0x60C2 is not in
  the object list [pp. 402–403].

## State machine

- **0x000F in Ready to switch on goes through to Operation enabled (T3 + T4).** Delta's own
  command table shows it [p. 412].
- **The transition table lists T16**: from Quick stop active, Enable operation with no alarm
  pending restarts motion [p. 412]. There is no 0x605A to choose this, so the manual is the
  only evidence for it. Test it on the drive before relying on it.
- **Quick stop has two ramps.** Controlword bit 2 = 0 ramps on 0x6085. A limit switch also
  counts as a quick stop, but ramps on the time that P5.003 selects [p. 412]. P5.003 points
  each event at one of P5.031–P5.035. The factory setting uses the short ones: 30 ms or 50 ms
  from 3000 rpm [pp. 305–307]. The end state after a quick stop is not stated.
- **Halt (bit 8) is named in the controlword table and nothing else** [p. 411]. There is no
  0x605D.
- **At a hardware limit switch the statusword looks like Quick stop active by default.**
  P3.019.A = 0 clears bit 5 and keeps the servo on. 1 sets Fault and turns the servo off. 2
  sets Fault and keeps it on. Bit 7 (warning) and bit 14 or 15 come on as well [p. 292]. A limit
  alarm (AL014/AL015) also has to be cleared before the axis may back off, unless
  P3.012.U = 1 [p. 290].
- **STO raises a fault by default.** With P1.120 = 3 (the default), STO gives AL500, Fault
  (bit 3) and 0x603F = 0x9000. Restarting needs a fault reset, then 0x6 → 0x7 → 0xF. With
  P1.120 = 2, which Delta recommends, STO sets only the warning bit (bit 7), and no reset is
  needed [p. 257].
- **The controlword defaults to 0x0004 and 0x6060 to 0 (no mode)** [pp. 410, 414].

## Option codes and fault reaction

| Object | ASDA-A3-EP | Differs from the profile |
|---|---|---|
| 0x605A quick stop | absent | see the two ramps above |
| 0x605B shutdown | 0 (default), −1 | **0 = coast with no dynamic brake; −1 = dynamic brake.** Both apply at servo off, and neither is a ramp |
| 0x605C disable operation | absent | — |
| 0x605D halt | absent | — |
| 0x605E fault reaction | absent | set by P1.032, per alarm group |

[pp. 402, 414]. **The fault reaction is P1.032, not 0x605E.** It sorts alarms into four
groups. Some stop by dynamic brake or coasting. Encoder faults use an open-loop torque stop.
Other alarms ramp on the P5.003 time. Overcurrent and STO always coast. Bits 4–5 choose what
holds the stopped motor (dynamic brake or free run). The default is 0x0060 [p. 241].

## Modes of operation

- **1, 3, 4, 6, 8, 9 and 10.** No vl (2) and no IP (7). 0x6502 = 0x03AD [pp. 370, 414, 450].
- **Statusword bit 12 in CSP, CSV and CST means "mode in effect"** [p. 414]. Bits 14 and 15
  are the positive and negative limit switches. P3.019.Z = 1 turns bit 14 into a SYNC_OK flag
  instead [pp. 413, 292].
- **0x6086 is read-only and is always 0** (trapezoid only) [p. 427]. S-curve smoothing is a
  drive parameter, P1.036 [p. 242].
- **Target reached in CSP uses P1.054 (0x2136), in encoder pulses**, not 0x6067. The default
  is 167772 pulses, 0.01 rev [pp. 391, 247]. 0x6067/0x6068 are documented for PP only [p. 417].

## Units and scaling

- **No 0x608F, 0x6091 or 0x6092.** Position scaling is 0x6093 "Position factor". Its
  sub-indices are the E-gear ratio P1.044 (numerator) and P1.045 (denominator), and the
  position is in PUU [pp. 403, 428].
- **The E-gear works on a fixed 2²⁴ pulses per revolution**, whatever the encoder resolution
  [p. 212]. Allowed range: 1 ≤ N/M ≤ 262144; numerator up to 2²⁹−1. Do not change it with the
  servo on [pp. 244–245]. **Changing it, or the direction bit P1.001.Z, moves the absolute
  origin**: home again [p. 348].
- **0x6063 and 0x60FC are in drive pulses, 0x6062 and 0x6064 in PUU** [pp. 415, 447]. How
  0x60F4 is computed depends on P3.018.B [p. 368].
- **Velocities are in 0.1 rpm, not user units**: 0x60FF, 0x606C, 0x606B, 0x60B1, 0x6099 and
  0x607F [pp. 418–419, 425, 439–440, 449]. P3.018.X switches 0x60FF/0x606C to pulse/s, and
  P3.018.C does the same for 0x607F/0x6080 [p. 368]. **0x6080 is in whole rpm** and is
  P1.055 [p. 425]. **0x6081 (profile velocity) is in PUU/s**, so PP and PV use different
  velocity units [p. 425].
- **Accelerations are times, in ms from 0 to 3000 rpm**: 0x6083, 0x6084, 0x6085, 0x609A,
  0x60C5 and 0x60C6 [pp. 426, 440, 445]. 0x6087 is in ms from 0 to 100 % rated torque
  [p. 427]. A larger value means a gentler ramp.
- **Torque in 0.1 % of rated torque.** 0x6071 and 0x6072 go up to 3500; 0x60E0/0x60E1 only up
  to 3000 [pp. 420–421, 446].
- **0x6065 defaults to 50331648 PUU** (3 rev at gear 1:1). Beyond it the drive raises AL009
  [p. 416].

## Homing

- **0x6098 takes −4 to 35.** **37 is not accepted**; 35 sets the current position as home
  [pp. 429, 438]. Methods 15, 16, 31 and 32 are reserved [p. 429].
- **Negative methods are hard-stop homing**, which Delta also calls "methods 36–39":
  **−1/−2 hard stop then index pulse; −3/−4 hard stop only** [pp. 429, 438]. The direction of
  each is shown only in the figure on p. 438, and the text extract does not give it. Read the
  figure before use. The 0x6098 text also says methods "36, 37" look for the index pulse; that
  means −1/−2 [p. 429].
- **Hard-stop detection is P1.087 (torque level, % of rated) and P1.088 (time, default
  2000 ms).** **P1.087 defaults to 1 %**, so set it before the first run. The motor may push
  about 10 percentage points above P1.087 [p. 252]. Delta advises the index variants, since a
  hard stop does not repeat exactly [p. 252].
- Homing also sets the absolute origin on an absolute encoder [p. 349].

## PDO mapping

- **Four RxPDOs (0x1600–0x1603) and four TxPDOs (0x1A00–0x1A03), up to 8 entries each**
  [pp. 376, 406–407]. **Only one of each can be assigned**: 0x1C12/0x1C13 sub-index 0 is 0 or
  1 [p. 408].
- **The default is 0x1601/0x1A01**: controlword, 0x607A, 0x60FF, 0x6071 and 0x60B8 out;
  statusword, 0x6064, 0x606C, 0x6077, touch probe status and 0x60BA, and 0x60FD back. **0x6060
  and 0x6061 are not mapped**: set the mode by SDO, or use 0x1602/0x1A02. 0x1603/0x1A03 is
  Delta's suggestion for Omron masters [pp. 376–377, 408].
- **The manual contradicts itself on PDO size.** The mapping objects carry a note that a PDO
  cannot exceed 64 bits [pp. 406–407]. Yet the default 0x1601 is 112 bits, and p. 376 speaks of
  8 × 32-bit entries [pp. 376, 378]. The ESI file is the safer guide.
- **Any drive parameter Pa.bcd is object 0x2aBC**, with BC the hexadecimal form of bcd
  (P1.044 → 0x212C). These Delta objects are PDO-mappable [pp. 402, 409]. **Writing one by SDO
  stores it in EEPROM.** A PDO write does that only with P3.011.X = 1, which Delta warns wears
  out the EEPROM [p. 290].
- **0x1003 entries hold the Delta alarm number in the high word** and the CiA error code in
  the low word [p. 405].

## Touch probe

- **Probe 1: DI1 or the index pulse. Probe 2: DI2 only.** The DIs have a 5 µs hardware
  response [p. 396]. P3.026 chooses the main or the auxiliary encoder as the latch source
  [p. 293].
- **With the index pulse as source, the edge bits are ignored.** It latches on the rising edge
  into 0x60BA [p. 396].
- **Using DI1 or DI2 as a probe overwrites its function code with 0x0100** [p. 396].
