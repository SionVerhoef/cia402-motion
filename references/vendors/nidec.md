# Nidec Control Techniques SI-EtherCAT (Unidrive M, Digitax HD)

**Read 2026-11-08**: Control Techniques *SI-EtherCAT User Guide*, part number 0478-0152-05,
issue 5 (copyright date 2 August 2021). Control Techniques publishes its manuals at
http://www.controltechniques.com/support. Page numbers are given in brackets.

SI-EtherCAT is an option module, not a drive. The CiA 402 profile runs in the module and drives
the host drive through its parameters, so what works depends on the host and its motor-control
mode (open loop, RFC-A induction, RFC-S servo). The module's firmware is in Pr S.00.002, the
host's slot menu [pp. 10, 153]. A few behaviours changed at module firmware V01.06.02 [p. 104].

## Which host does what

- **Supported hosts**: Unidrive M200/M201, M300, M400, M60x/M70x/M88x/HS7x, Commander
  C200/C300, Digitax HD [p. 10].
- **CSP, CSV and IP need a Unidrive M600 or above in RFC-A or RFC-S.** Not in open loop or regen
  [pp. 82, 99, 102]. CST needs M600 or above [p. 103]. **PP needs a Unidrive M70x or Digitax HD
  in RFC-A or RFC-S** [p. 106]. Touch probe: M70x and Digitax HD in RFC-A/RFC-S only [p. 73].
- **0x6502 shows what the host offers**: vl is always set; PP and HM need the host's AMC (motion
  controller); IP, CSP and CSV need the AMC plus the synchronisation signal; CST needs
  synchronisation and current feedback [p. 82].
- **On M200–M400 and Commander C200/C300 the module's task runs every 5 ms, unsynchronised** to
  the drive [p. 115]; the guide gives 4 ms as the best update time there [p. 19].
- **There is no profile velocity mode (3).** The modes are 1, 2 (vl), 6, 7, 8, 9 and 10
  [pp. 56, 67].

## Identity changes with the drive mode

**The product code 0x1018:02 includes the host's drive mode**, so switching the drive between
open loop, RFC-A and RFC-S changes it. A master that checks the product code then drops the
slave. Setting Pr S.00.049 to "Mode Agnostic" holds that byte at 0 [p. 33]. 0x1000 bits 16/17
(frequency converter / servo) also follow the mode [p. 32]. S.00.049 can also make the module
report itself as a Unidrive SP [pp. 34, 121].

## State machine

- **Nothing moves until the slave is in EtherCAT OP.** If it drops back to Pre-Op from any state
  from Switch on disabled up to Quick stop active, the profile falls to Not ready to switch on,
  after stopping by the configured method [p. 59].
- **0x000F in Ready to switch on goes on to Operation enabled by itself** (T3 and T4) [p. 57].
- **Statusword and mode display are refreshed every 40 ms**; some statusword bits faster
  [pp. 57, 68]. Quick stop and shutdown react fast only in CSP, CSV, CST and homing, halt only
  in homing; otherwise they wait for the 40 ms background loop [pp. 63–65]. Poll the
  statusword for the new state; the guide advises against a fixed delay [p. 57].
- **A fault reset from the drive's keypad leaves the statusword in Fault.** Reset over the
  controlword [p. 58].
- **Pr S.00.033 = On takes control away from the module** (stopping first as 0x605E says if the
  drive is running) and gives it back to local control [p. 134].

## Option codes

| Object | SI-EtherCAT allows | Default | Differs from the profile |
|---|---|---|---|
| 0x605A quick stop | 0, 1, 2, 5, 6 | 2 | no 3, 4, 7, 8 |
| 0x605B shutdown | −1, 0, 1 | 0 | **0 ramps, then disables**; −1 disables at once; 1 ramps and waits for the brake |
| 0x605C disable operation | 0, 1 | 0 | default 0: no ramp |
| 0x605D halt | 0, 1, 2 | **0 = no action** | halt (bit 8) does nothing until set to 1 or 2 |
| 0x605E fault reaction | 0, 1, 2 | 2 | ignored when the drive itself trips |
| 0x6007 abort connection | −3 to 3 | 1 | −1, −2, −3 do 1, 2, 3 and then trip the drive |

[pp. 63–66]. The meaning of 0x605B = 0 is the trap: on most drives it switches off at once,
here it ramps first. Setting Pr S.03.010 to "Controlled Stop" replaces the profile's ramps with
the drive's deceleration rate 8 (Pr 02.028) [p. 63]. 0x605E is also the reaction to a PDO loss
[p. 65].

## Modes of operation

- **0x6060 defaults to 2 (vl) in open loop and 8 (CSP) in RFC-A/RFC-S** [pp. 59, 67].
- **A mode change happens only at zero speed.** 0x6060 is read in every state, every 40 ms; an
  invalid mode, or one whose data is wrong, is refused and 0x6061 keeps the old mode [pp. 59–60,
  66].
- **CSP, CSV, CST and IP need distributed clocks.** Without them the module may drop to SafeOp
  [pp. 82, 100, 115]. The SYNC0 cycle is 250 µs or a multiple of it [p. 47].
- **0x60C2 must be 250 µs, 500 µs or a whole number of ms**, and is read at T3 [p. 100].
- **0x6086 = −1 in CSP extrapolates** from the last two targets when a PDO is missing; 0, the
  default, holds the last target [p. 101]. With extrapolation off, a lost PDO in CSP holds the
  axis where it is, which can look like a stop [p. 53].

## Cyclic data loss (0x3005)

The module watches its PDOs itself, on top of the EtherCAT watchdog. **With the default timeout
0x3005:1 = 0, the first late or missing PDO acts**: the default action 0x3005:2 = 0 raises a
warning and stops by 0x605E [pp. 53–55]. A master whose frames arrive late in the cycle, for
example with a wrong shift time, gets stops that look random. 0x3005:3 counts late PDOs
[p. 54].

## Homing

- **Methods 1–14, 17–30, 33, 34, 35 and 37.** 35 is marked legacy and equals 37; neither needs
  Operation enabled [pp. 95, 98]. **No negative (manufacturer) methods**: 0x6098 is an unsigned
  8-bit object, range 0–37 [p. 98].
- **0x6098, 0x6099, 0x609A and the homing source 0x3003 are taken at T3** (Ready to switch on →
  Switched on) [pp. 96–99]. Changing the method in Operation enabled has no effect until the
  drive goes through Switched on again.
- **The home switch is a drive digital input chosen in 0x3003:01** (default input 5), or any
  parameter via 0x3003:03/04; the index source is the encoder marker or a freeze input
  (0x3003:02) [p. 96].
- **The gear ratio 0x6091 is not used in homing** [p. 70].

## Units and scaling

- **0x608F is read-only**, taken from the encoder's normalisation turns; its motor-revolutions
  sub-index is always 1 [pp. 70–71]. 0x6091 and 0x6092 are SDO-only, not PDO-mappable [p. 70].
- **New 0x6091, 0x6092 and 0x3004 values take effect only at T3** (Ready to switch on → Switched
  on). If the combined ratio does not fit 1 to 2³¹−1 the module trips ("Scaling failure", or
  "APLS Failure" for 0x3004) and keeps the old ratio [pp. 52, 60, 70].
- **0x60FF and 0x606C are in user position units per millisecond**, not per second [p. 102].
  0x60B1 velocity offset is in 0.001 rpm [p. 103]. vl mode (0x6042–0x604C) is in rpm unless the
  vl factors say otherwise [pp. 85–86, 91].
- **0x6071, 0x6073, 0x6077, 0x6078 and 0x60B2 are in 0.1 %**, of the drive's own torque and
  current references [pp. 103–105]. 0x6077's source parameter changed at module firmware
  V01.06.02 [p. 104].
- **0x6080 max motor speed (rpm) writes the drive's maximum reference clamp Pr 01.006** and
  the position-loop speed clamp [pp. 60, 80].
- **Order matters in a start-up list**: some objects are converted using motor, encoder and
  scaling parameters, so those go first [p. 31].
- **0x6064 stays continuous over an encoder rollover only while the module tracks it.** A power
  cycle, a drive or module reset, a change to vl or CST, or leaving OP loses the count [p. 78].

## Monitoring defaults

0x6065 following error window and 0x6067 position window both default to 2³¹−1: until they are
set, no following error is raised and target reached ignores where the axis actually is
[p. 79]. 0x60FB is marked "do not use" [p. 81].

## Profile position

- **Bit 9 = 1 with bit 5 = 0 (change on set-point) is not supported**; the set-point is ignored
  [p. 107].
- **A set-point that changes velocity, acceleration, deceleration or jerk is acknowledged at
  least 4 ms late** [p. 107].
- **Rotary axes use 0x607B with its minimum fixed at 0** and only bits 6–7 of 0x60F2. With a
  direction set in 0x60F2, relative moves are refused [pp. 110, 113–114].
- 0x6086 = 3 gives jerk-limited moves with 0x60A4 [pp. 101, 112].

## PDO mapping

- **One PDO per sync manager**, up to 12 objects of any size [pp. 19, 34]. SM2/SM3 carry the
  synchronous pair; SM4/SM5 an optional free-running pair (≥ 2 ms; up to 32 objects in PDO 6)
  [pp. 44–46].
- **The default assignment is RxPDO 6 / TxPDO 6, the vl velocity pair** (0x1605: controlword and
  0x6042; 0x1A05: statusword and 0x6044) [p. 45]. For CSP or CSV, assign or remap a PDO yourself.
- Mapping objects available: 0x1600–0x1602, 0x1604, 0x1605, 0x1607 (regen only), 0x1609 (FSoE
  only), and the matching 0x1Axx [pp. 34, 39]. Mapping is checked at Pre-Op → SafeOp [p. 34].
- **Any drive parameter is an object**: index 0x2000 + 0x100 × slot + menu, sub-index =
  parameter number; bit parameters map as SINT, and a negative value writes 0 [pp. 29, 18].

## Touch probe

Touch probe 1 only (0x60B8–0x60BB): drive digital input 4 or 5, or the encoder marker (0x60D0)
[pp. 73–75]. Configuration changes take effect when the profile leaves Operation enabled or
Quick stop active [p. 76].
