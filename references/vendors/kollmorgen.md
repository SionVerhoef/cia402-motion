# Kollmorgen AKD (EtherCAT, firmware 1.17)

**Read 2026-11-08**: Kollmorgen, *AKD EtherCAT Communication*, edition P, October 2017, valid for
firmware 1.17, part number 903-200005-00. Page numbers in brackets are from this manual.
Kollmorgen publishes its manuals through https://www.kollmorgen.com (kdn.kollmorgen.com in the
manual's footer).

For firmware differences only: *AKD EtherCAT Communication*, edition D, April 2011, "valid for
hardware revision C" (no firmware version given), same part number. Cited as [D p. N].

This page covers the **AKD with onboard EtherCAT (CoE)**. AKD2G, AKD-N and the CANopen variant
were not read. The AKD is a WorkBench/Telnet drive with CiA 402 mapped onto its own parameters
(`DRV.OPMODE`, `HOME.MODE`, `MT.P` …); many profile objects are just another name for one of
them [pp. 86–90]. Where the manual contradicts itself, both pages are given below.

## FBUS.PARAM05 changes what the profile means

One vendor parameter, FBUS.PARAM05, switches several behaviours that a master assumes are fixed.
The manual gives each bit but **not the default value** of the parameter [pp. 16–17]. Read it on
the drive before porting code.

| Bit | Set (1) | Clear (0) |
|---|---|---|
| 0 | faults reset only by controlword bit 7 | Telnet or a digital input can also reset, and the state machine follows |
| 1 | hardware enable going low does not change the CiA 402 state | hardware enable low drops Switched on / Operation enabled to Switch on disabled |
| 2 | WorkBench/Telnet cannot enable the drive while the bus is Operational | they can |
| 4 | position, velocity and acceleration scaled by the CiA 402 objects | scaled by the AKD `UNIT` parameters |
| 8 | Switched on = power stage **off** (as in the profile) | Switched on = power stage **on** |
| 10 (only with bit 8) | Switched on reachable without DC bus voltage | without DC bus the drive stays in Ready to switch on |

[pp. 16–17; table in own words, bits 3, 5–7, 9, 11, 13 left out]. Bit 8 = 0 is the one that
surprises: the manual's own state description has the amplifier already enabled in Switched on,
with setpoints only taken after a rising edge on controlword bit 3 [p. 39].

## State machine and stopping

- **0x605A takes 1, 2, 5 and 6; the default is 2** (quick-stop ramp, then Switch on disabled)
  [pp. 86, 135]. 0, 3, 4, 7 and 8 are not offered. With the default, T16 (0x000F back from Quick
  stop active) is not available. The manual does not say which object sets the "slow-down" or the
  "quick-stop" ramp; the controlled-stop parameters are vendor object 0x3440 (sub 1 `CS.DEC`,
  sub 2 `CS.VTHRESH`, sub 3 `CS.TO`) [p. 71].
- **0x605B, 0x605C, 0x605D, 0x605E, 0x6007 and 0x6085 are not in the object dictionary**
  [pp. 86–90]. Stop-then-disable versus disable-at-once is the vendor object 0x35FF
  (`DRV.DISMODE`) [p. 80].
- **Controlword bit 8 halts in every mode**, and the mode's setpoints are kept [pp. 40, 133].
  There is no 0x605D to choose how.
- **0x000F in Ready to switch on**: the manual lists T3 and T4 separately and does not say
  whether one controlword does both [pp. 40, 132]. Send 0x0007, wait for Switched on, then
  0x000F.
- **Statusword bit 8 is STO** in the object description [p. 133] but "manufacturer-specific
  (reserved)" in the profile chapter [p. 41].
- **Statusword bit 9 (remote) follows `FBUS.REMOTE`**: 1 by default; Telnet sets it to 0 for
  tuning or commutation finding, to tell the master it is not in charge [p. 134]. The profile
  chapter says it is always 1 [p. 41].
- **Statusword bit 12 in CSV and CST** is described as staying 1 while the drive follows the
  setpoints, the same wording as CSP [p. 134].
- **Synchronisation supervision is on by default for EtherCAT** (FBUS.PARAM04 = 1). Seven missed
  frames while enabled raise F125 (emergency code 0x8780) [pp. 16, 63]. Communication loss is
  F702 (0xFF01) [p. 63]. There is no 0x6007 to choose the reaction.
- **0x345A lets the master drive the holding brake**, overriding the drive's own brake logic.
  Sub 1 bit 0 needs a rising edge to take control and is cleared by a fault; bit 1 applies (0)
  or releases (1). Sub 2 reports brake, STO and hardware-enable status. The drive takes the brake
  back if the bus is lost [pp. 126–127].

## Modes of operation

- **The manual gives three different mode lists.** 0x6060/0x6061 accept 1, 3, 4, 6, 7, 8, 9 and
  10, plus vendor modes −1 (analog current), −2 (analog velocity) and −3 (electronic gearing)
  [pp. 136–137]. The "supported operation modes" table lists only 1, 3, 4, 6, 7, 8 [p. 51].
  0x6502 defaults to 0xE5: pp, pv, hm, ip, csp, with no tq, csv or cst [p. 168]. Read 0x6502 on
  the drive and test 9 and 10 before relying on them.
- **Each profile mode is an AKD `DRV.OPMODE` plus `DRV.CMDSOURCE`**: pv = 1/1, ip and csp = 2/1,
  pp and homing = 2/0, torque = 0/1 [p. 51]. Profile position runs AKD motion task 0 [p. 51].
- **Change mode only at standstill**, and write the new mode's setpoint again after the change
  [p. 136]. If position or jog mode is stored, the drive comes up in homing after a reset
  [p. 136].
- **Interpolated position: linear only** (0x60C0 = 0), one setpoint in 0x60C1:1, buffer of up to
  10 [pp. 153–156]. A setpoint in 0x60C1 is only taken with controlword bit 4 set [p. 154].
- **Torque**: 0x6071 and 0x6077 are in 0.1 % of rated torque [p. 139], but the mode table says
  torque is commanded in % of the drive's peak torque [p. 51]. 0x6077 actually reports current
  (`DRV.ICONT`) [p. 139]. 0x6087 cannot be set below about 2385 ‰/s [p. 143].
- **0x60E0 and 0x60E1 are read-only** (they report `IL.LIMITP` / `IL.LIMITN`) [p. 89]. Limit
  torque through 0x6072, which some fixed PDOs carry [pp. 42, 87].

Rev D (2011) lists only pv (3), ip (7) and homing (6) [D p. 36].

## Units and scaling

- **Two scaling systems, chosen by FBUS.PARAM05 bit 4** (above). With bit 4 clear, position,
  velocity and acceleration follow WorkBench's `UNIT` settings and pv velocities are in
  0.001 rpm; 0x204C (pv scaling factor) only acts with bit 4 set [pp. 17, 120].
- **"Float scaling" column**: an SDO value maps to a WorkBench decimal parameter with a fixed
  factor. 1:1 means the integer is the WorkBench value; 1000:1 means the integer is the value
  × 1000 [p. 65]. 0x606C and 0x60FF are 1000:1 [pp. 87, 90].
- **0x606C: SDO in user units, PDO in rpm** (with the 1000:1 factor) [p. 138].
- **0x6063 and 0x6064 can differ between SDO and PDO.** 0x6063 is in increments, 2^`FB1.PSCALE`
  per turn (default 2²⁰); its SDO value follows the `UNIT` parameters unless FBUS.PARAM05 bit 9
  is set [pp. 17, 137]. 0x608F:1 accepts powers of two only [p. 143].
- **0x6092:1 is `UNIT.PIN`** [p. 88]. 0x6091 and 0x6092 both default to 1/1 [pp. 144–145].
- **Latch and touch-probe positions** are scaled like 0x6064, or like 0x6063 with FBUS.PARAM05
  bit 7 [p. 17].
- **0x6065 = 0 switches following-error monitoring off, and 0 is the default** [p. 138].
- **0x607D defaults to 0 (off)**, and changed limits need a save and a restart to take effect
  [p. 141].

## Homing

0x6098 is an INT8 that sets `HOME.MODE` and `HOME.DIR`; its default is 0 [pp. 88, 146].

- **Standard methods offered: 1, 2, 8, 12, 17, 18, 24, 28, 33, 34 and 35** [pp. 146–147]. 3–7,
  9–11, 13, 14, 19–23, 25–27, 29 and 30 are "not supported". **35 sets home at the current
  position; 37 is not listed** (36–127 reserved).
- **33 and 34 work on feedback without an index**: the drive homes within one turn
  (`HOME.MODE` 7) and uses the index (`HOME.MODE` 11) only if the feedback has one [p. 147].
- **Vendor methods**: −3 and −4 home on the reference switch with a fast search (0x6099:1) and a
  slow final approach (0x6099:2), −3 negative and −4 positive by their description; the table
  gives `HOME.DIR` = 0 for both [p. 146]. −5 sets home at the current position **and stores it
  in NVRAM**. −6 and −7 find the home input (positive / negative) and then the next feedback zero.
  **−1, −2 and 0 are reserved.** No method homes on a hard stop; `HOME.IPEAK` (homing current
  limit) is a vendor parameter [pp. 80, 86].
- The description of 18 reads "negative limit switch, positive direction" with `HOME.DIR` = 1
  [p. 147]; the profile's 18 is the positive limit switch. Test the direction.
- **Bit 10 (target reached) in homing uses `HOME.TPOSWND`** (0x5406), in pp `MT.TPOSWND`
  [pp. 86, 134].
- 0x6099:1 defaults to the equivalent of 60 rpm, 0x6099:2 to half of 0x6099:1 [pp. 147–148].

## PDO mapping and cycle time

- **Fixed maps are selected by writing one index to 0x1C12:1 / 0x1C13:1**: RxPDO 0x1701
  (position + controlword), 0x1702 (velocity + controlword), 0x1720–0x1725; TxPDO 0x1B01,
  0x1B20–0x1B26 [pp. 42–43, 110–111]. The ESI defaults are 0x1701 and 0x1B01 [pp. 44, 110–111].
  0x1724 and 0x1725 carry 0x607A for CSP; 0x1720–0x1723 carry 0x60C1:1 (ip) [p. 42]. None
  carries 0x6060/0x6061.
- **0x1701's position command changed in the ESI**: up to firmware 1.8.x the ESI named 0x6062
  (which the firmware does not support); from 1.8.5.0 it names 0x60C1:1, and a separate
  `AKD_TwinCAT.XML` is shipped for TwinCAT 2 [p. 42]. An old project or ESI may show 0x6062.
- **Free mapping: up to four RxPDOs 0x1600–0x1603 and four TxPDOs 0x1A00–0x1A03, 8 bytes each**;
  the manual gives the totals as 20 bytes Rx and 32 bytes Tx [p. 44]. The AKD's CoE is its
  CANopen implementation underneath.
- **A PDO of odd length is refused.** Pad Rx with the dummy 0x0002:0 (8 bit) and Tx with one
  sub-index of 0x2002:1–4. This is what makes the 8-bit 0x6060/0x6061 mappable [p. 44].
- **Objects marked with an asterisk only act in Operation enabled**: 0x6071, 0x6072, 0x60B1,
  0x60B2, 0x60C1:1, 0x60FF, 0x60E0, 0x60E1 [pp. 65, 87–90].
- **Cycle time**: 0x60C2 (units × 10^index s) sets `FBUS.SAMPLEPERIOD` in 62.5 µs steps; both
  sub-indices must be written. Default 2 ms [pp. 51, 155]. The object description says only
  multiples of 1 ms are allowed [p. 155]; the cycle-time table gives ≥ 250 µs for all
  interfaces [p. 51].
- **DC is not required**: without it the AKD locks to the SyncManager 2 event [p. 52]. The
  drive-side PLL is switched by FBUS.PARAM02 [pp. 16, 52].

Rev D (2011) listed fixed maps that Rev P no longer does: 0x1703 (torque command + controlword)
and 0x1B02; and it had no 0x1722, 0x1724, 0x1725 or 0x1B22–0x1B26 [D p. 35].
