# Lenze

**Read 2026-10-26**:

- **[AKB-SOD]** Lenze knowledge base 202600119, "CiA402: State machine is stuck in 'switch on
  disabled'" (last updated 2026-08-18, machine-translated), https://www.lenze.com/en-de/go/akb/202600119/1
- **[i950-TC]** Lenze knowledge base 202500375, https://www.lenze.com/en-us/go/akb/202500375/1,
  and the guide attached to it: "Commissioning example i750 and i950 with TwinCAT3" V1.1
  (2025-12-18), §2, §2.3, §4, §5, §8.2
- **[i950-CS]** Lenze knowledge base 202500394, https://www.lenze.com/en-de/go/akb/202500394/1,
  and its guide "Commissioning example i750 and i950 with Codesys V3" V1.0 (2025-12-15),
  https://download.lenze.com/AKB/English/202500394/Commissioning_example_i750_and_i950_with_Codesys_V3_V10_EN.pdf

**Read 2026-11-08**, Lenze manuals (www.lenze.com, download area). Page numbers are the PDF's
own page numbers:

- **[i700]** *i700 servo inverters, Reference manual*, DMS 7.0 EN, 05/2019 (E70ACM…, EtherCAT)
- **[i750]** *i750 cabinet servo inverter, Commissioning, CiA 402*, 4.0 EN, 03/2024
- **[i950]** *i950 cabinet servo inverter, Commissioning, CiA 402*, 12.0 EN, 11/2024
- **[i950-adv]** *i950 cabinet servo inverter, "CiA 402 advanced" technology application,
  Commissioning*, 5.0, 10/2023

## i550 motec and i650 motec: stuck in Switch on disabled

[AKB-SOD] The fieldbus part of these drives (iSM) can stay in **Switch on disabled** when it
should go on to Ready to switch on. The conditions:

- CiA 402 operation with velocity mode (0x6060 = 2)
- a controlword that stays unchanged
- then either a fault, or the mains supply switched off and on **while the 24 V control supply
  stays on**

The i550 cabinet and protec do not have the problem. TwinCAT NC waits for Ready to switch on,
never sends the transition again, and hangs. No root cause is given. **Fixed in firmware
version 4.7.0.13.** Before that firmware, Lenze's workaround is to trigger the transition by hand or
from PLC code. One way, our own example: write 0x0000 for a cycle, then 0x0006 again.

## i750 and i950 as CiA 402 drives

From the two commissioning guides [i950-TC, i950-CS] (firmware 1.13.0.3463 in the example):

- **Select the CiA 402 technology application first** (0x4000 = 0).
- Modes in the examples: CSP (with velocity offset, torque offset optional), CST (with velocity
  offset), CSV and velocity mode. PDO mapping is free. Both examples home in the controller, not
  with drive mode 6.
- **The default PDO set includes the velocity offset 0x60B1 and the torque limits 0x60E0/0x60E1,
  plus the Lenze words 0x2830, 0x2831 and 0x2833.** In CSP the drive needs the master's velocity
  in 0x60B1. In TwinCAT it must be linked to the NC axis by hand (the NC side is for
  **twincat-motion**). **0x60E0/0x60E1 must be written by the master** (in 0.1 %: 2000 = 200.0 %),
  or taken out of the mapping. Mapped and left at 0, they allow no torque.
- **With a motor brake, set 0x2820:1 = 0** (the brake follows the device state machine). Brake
  control through the controlword is not supported with a Beckhoff controller.
- **EtherCAT supervision**: losing Sync0 in DC mode drops the drive to Safe-Op with a fixed
  error. Missed PDO frames add 3 to a counter and good ones subtract 1. Reaching the threshold
  0x10F1:2 (Lenze recommends more than 5) raises error 0x8700. A bus disconnection raises 0x8181.
  One missed cycle is bridged by extrapolation, two in a row are not. Network-side diagnosis is
  for **ethercat-diagnostics**.

## What the manuals add: i700, i750, i950

The sections above come from knowledge-base articles. What follows is from the four manuals
read on 2026-11-08. Where the i750 and the standard i950 manual say the same, both are cited.

### Two technology applications on the i950

The i950 has a plain CiA 402 application and a **"CiA 402 advanced" application**. The advanced
one adds what the plain one lacks: homing mode 6, its own scaling (feed constant and gear
ratio) and a jerk-limited quick stop [i950-adv pp. 49–58]. The i750 and the plain i950 have
none of these [i750 pp. 489–490; i950 pp. 689–690]. Check which application a drive runs before
porting code to it.

### Modes

- **0x6060 takes 2 (vl), 8 (CSP), 9 (CSV) and 10 (CST)** on the i700, the i750 and the plain
  i950 [i700 pp. 217, 219; i750 p. 211; i950 p. 248]. There is no profile position, profile
  velocity, profile torque or interpolated position mode.
- **The advanced application adds 6 (homing)** [i950-adv p. 57].
- **Vendor modes: −12 pole position identification and −13 manual jog (open loop)** on the
  i750 and i950; 0x6061 can also show −10 (test mode) and −11 (identification) [i750 p. 211;
  i950-adv p. 57].
- **0x6060 defaults to 0** ("no selection") [i750 p. 489; i700 p. 220]. Write it, or map it, before
  enabling.

### State machine and stopping

- **0x605A takes only 2 and 6; the default is 2** (ramp, then Switch on disabled). 6 holds Quick
  stop active [i700 p. 219; i750 pp. 212, 489; i950 pp. 249, 689]. So with the default, T16
  (0x000F back from Quick stop active) is not available; the drive is already in Switch on
  disabled.
- **0x6085 defaults to 2147483647**, the largest value, which means a quick stop as steep as the
  drive can make it [i700 p. 220; i750 p. 490]. On the i700 its unit is position units per s²,
  set through 0x608F; the manual works an example from a ramp time [i700 p. 220].
- **0x605B exists on the i750 and i950 with 0 and 1 only; the default is 0**, which removes
  torque at once. 1 runs the quick-stop ramp first [i750 pp. 212, 489; i950 p. 249]. The i700
  has no 0x605B [i700 pp. 213–214].
- **There is no 0x605C or 0x605D** on any of the three [i700 pp. 213–214; i750 pp. 489–490;
  i950 pp. 689–690]. On the i750 and i950, controlword bit 8 (halt) ramps the speed to zero
  [i750 p. 213]. On the i700, bit 8 is "not specified" [i700 p. 218].
- **0x605E (minor faults / error class II) adds two vendor values: −2 (the default) and −3.** −2
  tries a quick stop and, if that cannot work (an encoder fault, for example), brakes with DC
  current or short-circuit braking; −3 is a variant for hoists. 0 and 2 are as in the profile
  [i750 pp. 212, 489; i700 p. 321]. If the reaction has not finished within 0x2826 (default 4 s),
  the drive goes to Fault [i750 p. 212].
- **Shutdown waits for the brake.** With automatic brake control, the drive waits for the brake
  closing time (0x2820:002) before it removes torque [i750 p. 215; i700 p. 222]. The i750
  manual makes an exception for velocity mode (vl) [i750 p. 215].
- **Controlword bit 14 releases the holding brake by hand**, even with the power stage off. The
  manual puts the responsibility on whoever drives that bit [i750 p. 213; i700 p. 218]. This is
  the brake control through the controlword that [i950-TC] says is not supported with a Beckhoff
  controller.
- **0x2DE0:014 can force controlword bit 4** to FALSE or TRUE. The manual gives no reason
  [i750 p. 213]. Compare CODESYS's `_bSetControlBit4InCSP` in `README.md`.
- **Statusword bits the profile leaves to the vendor:** bit 8 = cyclic RPDOs switched off (by
  0x2824), bit 14 = brake released, bit 15 = STO not active [i700 p. 219; i950-adv p. 57].
- The manuals do not say whether 0x000F in Ready to switch on goes straight to Operation
  enabled.

### Units and scaling

- **Velocity objects (0x60FF, 0x606C, 0x60B1) are in Lenze's "n-unit": 2³¹ = 480000 rpm**, so
  1 rpm is about 4474 units, whatever the encoder [i700 pp. 215, 266; i750 pp. 89, 490;
  i950-adv p. 700]. Engineering tools and the keypad show rpm; the PDO carries n-units
  [i750 p. 89]. 0x6042 and 0x6044 (vl) stay in plain rpm, 16 bit [i750 p. 489].
- **Position is encoder increments per motor revolution set in 0x608F**, a power of two from
  2¹⁶ to 2³⁰; the default is 16 bit (65536) [i700 p. 215; i750 p. 490].
- **Torque and current objects are in 0.1 %** of the rated value (0x6071, 0x6072, 0x6077,
  0x60E0, 0x60E1). 0x60E0/0x60E1 default to 100 %, 0x6072 to 250 % [i750 pp. 489–490].
- **No factor group: 0x6091, 0x6092 and 0x60A8–0x60AB are absent** [i700 pp. 213–214;
  i750 pp. 489–490]. The advanced application scales through its own parameters: feed constant
  0x500E:032 (default 65536) and gear ratio 0x500E:033/0x500E:034 [i950-adv pp. 50–51].
- **0x60C0 defaults to −1, a vendor value** for quadratic interpolation of the cyclic setpoint
  [i750 p. 490].

### Homing (advanced application only)

[i950-adv pp. 54–58]:

- **The standard method numbers 1, 2, 3, 5, 17, 18, 19, 21, 33 and 34 are offered.** For the
  methods using an index, the "touch probe" source is set in 0x503F:080: the encoder zero pulse
  or a digital input edge.
- **−1 and −2 home on the end stop by torque: −1 in the negative direction, −2 positive.** The
  reference is taken when the drive stands still for the blocking time (0x503F:079) with the
  torque above the limit (0x503F:078, in Nm). No index pulse.
- **0 sets the reference at the current position** (where the profile reserves 0); 35 and 37 are
  not in the list. **99 deletes the reference.**
- **Controlword bit 12 (rising edge) also deletes the reference**, a use of a bit the
  profile leaves to the manufacturer. Bit 4 falling cancels homing.
- After the reference, the drive can stop, or move by or to the position in 0x503F:072
  (0x503F:071).
- 0x6099:01/02 set the two search speeds; there is no 0x609A in the list. With speed 2 at 0
  (the default), the whole run uses profile set 1.

### Quick stop in the advanced application

0x503F:010 picks between the inverter quick stop (0, linear with 0x6085) and an application
quick stop (1, jerk-limited with 0x500D:048 and 0x500D:049). A digital input can trigger quick
stop too (0x5020:007) [i950-adv p. 52].

### PDO mapping and cycle times

- **Lenze ships one preconfigured PDO per mode**: RPDO 0x1600 (CSP), 0x1601 (CST), 0x1602
  (CSV), 0x1603 (vl), 0x1604 (touch probe), and 0x1606 (torque limits), with TPDOs 0x1A00–0x1A04
  to match [i700 pp. 27–28; i750 p. 54; i950 p. 61].
- **The CSP default carries more than the profile's minimum**: 0x2830 (Lenze control word),
  0x6060, 0x60B2 torque offset, 0x60B1 velocity offset and 0x2902 (speed-controller load I
  component) in; 0x2831, 0x6061, 0x603F, 0x606C, 0x6077, 0x60F4 out [i750 p. 54].
- **i700: one free mapping object per direction and axis (0x1605/0x1A05), up to 8 objects.**
  At most 32 objects and 100 bytes per direction. Lenze recommends the fixed ones
  [i700 p. 27]. The i750 and i950 manuals do not describe a free object; [i950-TC, i950-CS]
  map freely.
- **Cycle times: 0.25, 0.5 and 1 ms, then whole milliseconds up to 10 ms** [i700 p. 27;
  i750 p. 235; i950 p. 300].

### i700: two axes in one device

The i700 double-axis module puts axis B at **+0x800**: 0x6840 for 0x6040, 0x1610 for 0x1600,
and in the vendor area 0x3020 for 0x2820 [i700 pp. 27–29, 213–214]. The device has 0x6502 =
0x382 (vl, CSP, CSV, CST) [i700 p. 217].
