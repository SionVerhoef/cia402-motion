# STOBER SC6 / SI6 with the CiA 402 application

**Read 2026-11-08**: STÖBER Antriebstechnik, *CiA 402 – SC6, SI6, Operating manual*, ID 443080,
version .01 (09/2019). STOBER publishes its manuals at http://www.stoeber.de/en/downloads/. Page
numbers in brackets are PDF pages (the `=== page N ===` markers of the text extract). The manual
covers SC6 and SI6 drive controllers with DriveControlSuite (DS6) and firmware V 6.4-D or later
[p. 6], over EtherCAT.

The CiA 402 profile is an *application* loaded into the drive in DS6, not a fixed firmware
function. There are two: **"CiA 402"**, the incremental version (scaling done in the master;
recommended for TwinCAT), and **"CiA 402 HiRes Motion"**, which scales in the drive and sends
user units (recommended for STOBER's own MC6 controller) [pp. 21, 23, 122]. Every profile
object is backed by a STOBER parameter (group letter + line, e.g. controlword 0x6040 = A515,
statusword 0x6041 = A516, modes 0x6060 = A541) [pp. 110–112]. Parameter changes are not
retained over a power cycle until saved with A00 *Save values* [p. 18].

## Two axes in one device

SC6 and SI6 come as double-axis controllers. **Axis B's profile objects sit 0x800 higher**
(0x6840 controlword, 0x6841 statusword, 0x6860 mode …) [pp. 113–115], and its STOBER parameters
are 0x8000 higher than axis A's (0xA000–0xD3FF instead of 0x2000–0x53FF) [pp. 116–117]. Each
axis has its own PDO channel [pp. 22, 108–109].

## State machine

- **A hardware enable signal gates the state machine.** Transitions 2, 3, 4, 5, 6 and 8 need the
  enable signal (source chosen in A60) as well as the controlword command. Dropping it sends the
  drive to Switch on disabled (T7, T9, T10), or, in Operation enabled with A44 = active, into a
  quick stop (T11) [pp. 81–83]. A master that sends the right controlword and sees no state change
  should check this input first.
- **Quick stop active always ends in Switch on disabled** (T12) once the stop is done [p. 83].
  The manual describes no return to Operation enabled (T16). A quick stop command is also listed
  as a cause of Switch on disabled [p. 81].
- **Switch on disabled has a reason code**: E47 and E49 show why (no DC link, safety active,
  disable voltage, quick stop) [p. 81]. E48 shows the current device state [p. 80].
- **Brake release depends on the mode**: in CSP, CSV, CST, PV and PT at the first active motion
  command; in PP, IP and homing on the mode's own controlword bit [p. 83].
- **For a gravity-loaded axis with a brake, STOBER says to shut down by quick stop (T11)**, not by
  removing enable, so the load is held until the brake has closed [pp. 31, 79].
- The manual does not say whether 0x000F in Ready to switch on performs T3 and T4 in one step.

## Option codes

| Object | SC6 / SI6 | Differs from the profile |
|---|---|---|
| 0x605A quick stop | present (A536), RxPDO-mappable | **allowed values and default not given** |
| 0x605B shutdown | absent | not in the object list |
| 0x605C disable operation | absent | not in the object list |
| 0x605D halt | absent | halt (bit 8) still changes what PP/PV bit 10 means [pp. 91–92] |
| 0x605E fault reaction | present (A540) | values not given |

[pp. 110–112]. 0x6007 is not in the object list either. Read A536/A540 with the drive's ESI or
DS6 for the values actually supported.

## Modes of operation

- **Modes 1, 3, 4, 6, 7, 8, 9, 10 and the STOBER mode −1 (jog)** [pp. 45, 85–98]. No vl (2), no 5.
  The control-panel table also lists 0 (no mode) [p. 99].
- **Jog (−1) uses controlword bits 4 (positive) and 5 (negative)**; both set brakes to a stop.
  Speed, ramps and jerk come from I12, I13, I45, I18 [pp. 97–98].
- **Switching between a master-side mode (IP, CSP, CSV, CST) and a drive-side mode (PP, PV, PT)
  only at standstill**: |actual velocity| below the velocity window C40 (I199) [p. 98].
- **IP takes a single set-point**: 0x60C1 has one sub-index, and every 0x60C4 buffer sub-index is
  marked "no function" [pp. 85, 111–112].
- **A late set-point in IP, CSP or CSV is extrapolated** from the last increment, up to the time in
  I423; after that the drive faults (event 78, cause 3) [p. 104]. 0x60C2 (A602) is copied to A291,
  which must equal the drive cycle A150 or a multiple of it [p. 104].
- **Set-value monitoring is on by default**: a step the drive cannot follow trips "excessive set
  value jump". STOBER says to command ramps the axis can actually do [p. 30].
- **PP bit 6 = 1 (relative) is relative to the last target or to the actual position**, chosen by
  bits in 0x60F2 (A621) [pp. 91, 99].
- **Rotary range: 0x607B:01 has no function; 0x607B:02 is used as the revolution length**
  [p. 110]. 0x607E polarity: only bit 7 works [p. 110].

## Homing

- **Methods 1, 2, 3, 5, 7, 11, 17, 18, 19, 21, 23, 27, 33, 34 and 37**, plus −1 to −4 [pp. 54–55].
  Only one edge variant per switch case: no 4, 6, 8–10, 12–14 or their 20-series twins. **37 is
  the documented value; 35 is described as the same method** [p. 74]. Whether writing 35 to
  0x6098 is accepted is not stated. 0x60E3 lists the supported methods [p. 112].
- **Negative methods: homing on a torque/force limit.** −1 positive, −2 negative, no index; −3
  positive and −4 negative, then reverse to the index [pp. 55, 74–77]. The limit is reached when
  torque stays above I28 for the time in I29 [p. 74].
- **The axis stops just past the reference point; it does not move back to it** [p. 78]. At the
  reference point the actual position is set to 0x607C (A569) [pp. 56, 78].
- **Limit switches act as reversal points during homing, not as faults**; a limit switch that does
  not match the direction of travel raises a fault. Software limits are ignored while homing and
  apply only once the axis is referenced [p. 52].
- **Homing status bits: the manual gives 13/12/10 = 1 1 0 for "error at standstill"** [p. 95],
  where the profile has 1 0 1. This may be an error in the manual; check on the drive.
- Reference retention for multi-turn encoders is a drive feature (I46). With I46 = 5 *Direct
  absolute* the raw encoder position is reported from power-on, for master-side reference
  handling [p. 78].

## Units and scaling

- **Incremental application: 2²⁰ increments per motor revolution by default** (0x6092:01 =
  1048576, 0x6092:02 = 1), scaling done in the master [pp. 25, 40]. Position is DINT: 20 bits of
  single turn, 12 bits of multi-turn; past that the master must count overflows [p. 78].
- **HiRes Motion: scaling in the drive** through gear ratio 0x6091 (A584) and feed constant 0x6092
  (A585), with I06 decimal places and I09 unit; the master is told only the decimal places [p. 24].
- **0x6091 and 0x6092 are PDO-mappable** [p. 111]. No 0x608F and no 0x6093–0x6096 in the object
  list [pp. 110–112].
- **Velocity and acceleration have STOBER decimal-place settings**: A310 (velocity) and A311
  (acceleration/jerk) [p. 78]. The manual does not state the velocity unit or time base for
  0x60FF/0x606C.
- **Leave A213 *Fieldbus scaling* at 1 (raw value)** [p. 21].
- **Absent from the object list**: 0x6067 position window and 0x606D velocity window (STOBER uses
  I22/I87 and C40), 0x6080, 0x6086, 0x6073, 0x60E0/0x60E1 [pp. 25, 110–112].

## Limit switches

- **Limit switch inputs are active-low.** If both read inactive the drive faults (event 53, cause
  7) [pp. 50–51, 53]. Hitting a hardware or software limit raises event 53 and locks that direction
  (I196) [p. 49].
- **"Passable" limit switches**: the drive remembers where it passed the edge and treats the
  switch as active until it is back over that point; the memory is lost at power-off [p. 51].
- 0x607D software limits apply only on limited axes, only once referenced, and are off when both
  values are equal [p. 52].

## PDO mapping and the ESI

- **One free PDO channel per axis, up to 24 parameters**, any profile object or STOBER parameter
  (A225/A226 Rx, A233/A234 Tx); one more channel is reserved for FSoE [pp. 22, 35].
- **STOBER parameter as an object**: index = 0x2000 + group number × 0x200 + line, sub-index =
  array element (0 for simple parameters) [p. 116].
- **Default mapping (both applications)**: Rx: 0x6040, 0x6060, 0x607A, 0x60FF, 0x60B1, 0x60B2,
  0x6071, 0x60FE; Tx: 0x6041, 0x6061, 0x6064, 0x606C, 0x6077, 0x60F4, 0x60FD, 0x60E4, plus
  STOBER's status word 2 (E201) and user-defined status word (A67) [pp. 108–109]. The
  user-defined word carries 16 sources picked in A66 [p. 45].
- **For TwinCAT the ESI is generated by DS6 and must be re-exported after any PDO change**;
  TwinCAT reads one ESI per drive series [p. 36]. The PDO layout must also be changed on both
  sides (master and DS6) [p. 35].
- **PDO timeout A258**: 0 or 65535 = off; 65532 ignores one lost frame, 65533 three in a row
  [p. 21].

## Touch probe

Two probes, 0x60B8–0x60BD; sources chosen in I110 (probe 1) and I126 (probe 2) [pp. 105, 111].
