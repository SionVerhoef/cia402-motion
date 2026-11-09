# Yaskawa Sigma-V with SGDV-OCA01A EtherCAT (CoE) Network Module

**Read 2026-11-08**: Yaskawa Electric, *Σ-V Series AC Servo Drives, EtherCAT (CoE) Network
Module, Model SGDV-OCA01A, User's Manual*, manual no. SIEP C720829 04B, revision 1 (December
2010; first edition June 2009). Yaskawa publishes its manuals on its regional sites, for example
https://www.yaskawa.com and https://www.yaskawa.eu.com. Page numbers in brackets are **PDF
pages**, not the printed chapter-page numbers.

**This page covers the old Σ-V (Sigma-V) generation only**: the SGDV-E1 (rotary) and SGDV-E5
(linear) SERVOPACKs with the SGDV-OCA01A option module attached [p. 23]. The Σ-7 (Sigma-7)
EtherCAT drives were not read. Nothing here should be assumed to hold for them.

SGDV-OCA01A is a command option module, not a drive. The CiA 402 profile runs in the module and
drives the SERVOPACK through its parameters; Pn000–Pn6FF appear as Yaskawa's objects
0x2000–0x26FF (0x2100 = Pn100) [p. 107]. Several features depend on the module's revision
(0x1018:03): the Safety Module, statusword bits 8 and 15, and 0x2720 need 0x00030001 or higher
[pp. 55–56, 116]. 0x100A reports both module and SERVOPACK software versions [p. 96].

## Identity and bus

- **Vendor ID 0x539; product code 0x02200001 for SGDV-E1 (rotary), 0x02200002 for SGDV-E5
  (linear).** The two have separate ESI files [pp. 67, 99]. **0x1018:04 serial number is
  always 0** [p. 99], so a master cannot tell two modules apart by serial number.
- **No read-write datagrams: APRW, FPRW, BRW and LRW are not supported** [pp. 24, 66]. A master
  that combines inputs and outputs into one LRW frame must be set to use separate LRD/LWR for
  this slave.
- SM2/SM3 take up to 256 bytes each (200 bytes on modules up to revision 0x00020000), at fixed
  start addresses [p. 66]. Mailbox SDO only: no PDO over the mailbox [p. 24].

## State machine

- **0x000F in Ready to switch on goes straight to Operation enabled** (T3 and T4). The manual
  lists "Switch on + Enable operation" as its own command [pp. 76, 114], and its return
  procedure after a safe stop is Shutdown, then that combined command [p. 58].
- **Ready to switch on moves on only with main-circuit power on and EtherCAT in OP**, and not
  while the motor is being run from the digital operator or SigmaWin+ [p. 75]. Statusword bit 4
  shows main power [p. 116].
- **Losing main power or the /HWBB (safe torque off) input drops Switched on, Operation enabled
  and Quick stop active to Switch on disabled**, not to Fault [pp. 57, 75]. To recover: inputs
  back on, Shutdown, then 0x000F [p. 58].
- **Quick stop active falls to Switch on disabled by itself once the motor stops** [p. 75]. See
  0x605A: no option code keeps the drive in Quick stop active.
- **Leaving EtherCAT OP while in Operation enabled raises alarm A.A11** [p. 143].
- **Fault reset is controlword bit 7, 0→1, for alarms and warnings** [p. 114]. Many SERVOPACK
  alarms are marked not resettable and need a power cycle [pp. 139–142].
- Statusword bits taken by Yaskawa: **8 = active mode stop** (Safety Module's internal stop),
  **14 = torque limit active**, **15 = safety function active** [p. 116]. Controlword bits 11
  and 12 switch on the external torque limits Pn404/Pn405 (objects 0x2404/0x2405) [p. 114].

## Option codes

| Object | Allowed | Default | Differs from the profile |
|---|---|---|---|
| 0x605A quick stop | 0–3 described; range 0–4 | 2 | **every code ends in Switch on disabled**; no 5–8. 3 = stop on torque limit. 4 is in the range but its meaning is not in the text read |
| 0x605B shutdown | 0, 1 | 0 | 0 = power stage off; 1 = ramp on 0x6084 (0x609A in homing) |
| 0x605C disable operation | 0, 1 | 1 | as 0x605B |
| 0x605D halt | 1–3 described; range 0–4 | 1 | 1 ramp, 2 quick-stop ramp, 3 torque limit; stays in Operation enabled |
| 0x605E fault reaction | 0 only | 0 | servo off, motor free; the real stop is set by Pn001.0 / Pn00B.1 |

[pp. 118–120, 156]. **In profile torque and CST, quick stop, shutdown and disable operation
always act as code 0** (power stage off), and halt ramps the torque demand to zero
[pp. 118–120]. The texts for 0x605B and 0x605C both say the drive goes to Switch on disabled;
the profile sends them to Ready to switch on and Switched on. That looks like an error in the
manual, but it was not checked on a drive.

**Alarms stop by group, not by 0x605E**: Gr.1 alarms stop per Pn001.0 (factory: dynamic brake),
Gr.2 per Pn00B.1 (factory: zero-speed stop; Gr.1 method in torque control) [p. 139]. The
module's sync and state alarms (A.A10–A.A12) are Gr.2, or Gr.1 from module revision 0x00030001
[p. 143].

## Modes of operation

- **Modes 1, 3, 4, 6, 7, 8, 9, 10. No vl (2)**; 0x6502 = 0x03ED [pp. 121–122]. 0x6060
  defaults to 0; writing 2 or an unsupported value keeps the last mode [p. 121].
- **A mode change takes effect at once, even while moving.** Switching into PP, HM or IP with
  controlword bit 4 already 1 **starts the move or homing immediately**; the cyclic and profile
  velocity/torque modes start at once regardless [p. 77]. The master must update the mode's
  process data in the same cycle [p. 77].
- **A CSP or IP step larger than 4194304 inc/ms (after scaling) is ignored** and statusword bit
  11 (internal limit) is set [p. 117]. Bit 11 also covers software limits and P-OT/N-OT
  [pp. 64, 117].
- 0x60C2 can be changed only in Switch on disabled; with DC it is taken from the Sync0 cycle,
  in free-run the master must set it [p. 129].
- 0x6077 torque actual value is the torque reference, not a measurement [p. 132]. 0x6072 is set
  to the motor's maximum torque at power-up [p. 133].

## Units and scaling

- **No factor group.** 0x608F, 0x6091 and 0x6092 are not in the dictionary [pp. 94–95].
  Scaling is Yaskawa's own: 0x2701 position (1 pos unit = num/den inc), 0x2702 velocity (1 vel
  unit = num/den inc/s), 0x2703 acceleration (1 acc unit = num/den × **10⁴ inc/s²**)
  [pp. 22, 107–108]. The SERVOPACK's electronic gear is not used [p. 51].
- **With the defaults (all ratios 1), positions are raw encoder increments, velocity is inc/s
  and acceleration is 10⁴ inc/s².** On a 20-bit encoder, 1 rev/s is 1048576 velocity units
  [pp. 22, 108].
- **Ratio limits**: position 1/4096 < ratio < 4096, velocity 1/128 to 524288, acceleration
  1/128 to 16384; outside them, alarm A.A20 [pp. 107–108, 145].
- **New unit settings, and SERVOPACK parameters that need a restart, take effect only after a
  power cycle or writing 1 to 0x2700 in Switch on disabled** [pp. 51, 107]. 0x2700 also
  re-initialises all position values [p. 107].
- Torque objects are in 0.1 % of rated torque; 0x6076 is in mNm (mN for linear motors)
  [p. 132].

## Saving parameters

SDO writes are not saved by themselves. **Writing "save" to 0x1010 stores them**; sub-indices 1
and 4 only in Switch on disabled, and after them a power cycle or 0x2700 is needed before
Operation enabled [p. 97]. **Values written by SDO to an object that is also PDO-mapped are
overwritten by the PDO** [p. 52].

## Homing

- **Methods 0, 1, 2, 7–14, 24, 28, 33, 34 and 35. No 3–6, 17–23, 25–27, 29–32, no 37 and no
  negative methods**: 0x6098 is limited to 0–35 [pp. 82–84, 125, 157].
- **0x6098 defaults to 35** (current position), and is not stored in EEPROM [p. 125]. Write it
  at every start-up. 35 does not need Operation enabled [p. 84].
- **The limit switches are the overtravel inputs P-OT/N-OT; the home switch is input SI6
  (/Home); the index is the encoder C phase** [pp. 23, 82–84]. Hitting the wrong overtravel
  input in methods 1, 2, 7–14, 24, 28, 33, 34 ends homing with bit 13 set [p. 64].
- 0x6099 defaults to 500000 and 100000 vel units, which is inc/s until 0x2702 is set [p. 126].
- **With an absolute encoder, 0x607C is added to the position at power-up** (or at 0x2700)
  [pp. 54, 125].
- **Software limits 0x607D work only after homing or with an absolute encoder**, are shifted by
  0x607C, and are off while min ≥ max (both default 0) [p. 123].

## PDO mapping

- **Four RxPDO (0x1600–0x1603) and four TxPDO (0x1A00–0x1A03) maps of up to 8 entries; at most
  two PDOs per sync manager** [pp. 69, 100–104]. Mapping and 0x1C12/0x1C13 can be written only
  in Pre-Op [pp. 69, 100, 104].
- **The default assignment is 0x1601/0x1A01: controlword + 0x607A, statusword + 0x6064**, the
  CSP pair [pp. 70, 104]. It carries no 0x6060/0x6061, so the mode goes by SDO or a remap.
  0x1600/0x1A00 hold a general set (targets, 0x6072, mode, touch probe), 0x1602/0x1A02 the CSV
  pair, 0x1603/0x1A03 the CST pair [pp. 70, 100–103].

## Synchronisation

- **DC (Sync0) or free-run; DC cycle 125 µs to 4 ms in 125 µs steps** [pp. 24, 71]. 0x1C32:05
  reports 62.5 µs as minimum cycle, which the stated cycle range does not allow [p. 105].
- **Outputs become valid a fixed 125 µs after Sync0**; the input latch shift 0x1C33:03 is
  settable in 125 µs steps [pp. 71, 106].
- **0x10F1:02 counts missed frames: +3 per Sync0 without new outputs, −1 per good one; at the
  limit (default 9) alarm A.A12 and the slave drops to SafeOp** [p. 106]. With the default,
  three missed frames in a row are enough. 0 disables the check [p. 106].

## Errors and emergency

- **0x603F holds the SERVOPACK's own alarm or warning number**, not a CiA 402 error code
  [pp. 114, 139]. Every emergency message has error code 0xFF00 with the alarm number in the
  manufacturer field [p. 73].
- **Warnings reach 0x603F and the emergency only with Pn001.3 = 1** [p. 147].

## Touch probe

- **Probe 1: input SI4 or the encoder C phase. Probe 2: input SI5 only** [pp. 90, 134].
- **One sampling bit per probe, no separate negative edge**: bit 4/12 enables sampling (the
  edge is not stated), bits 5–7/13–15 are reserved, and there are no 0x60BB/0x60BD
  [pp. 134–135]. In continuous mode, status bit 7/15
  toggles on every new value [p. 135].
- **Probe 1 cannot be used during homing; starting homing switches it off** [pp. 90, 134].
