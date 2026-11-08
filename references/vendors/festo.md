# Festo CMMT-AS and CMMT-ST

**Read 2026-11-08**: Festo, *CMMT-AS-...-S1 Servo drive, Manual: Software, Function, Fieldbus,
Device profile*, document 8259155, version 2026-06p. It covers the CMMT-AS-...-MP-S1 from
revision 1 with firmware package CMMT-...-MP V37.1 or later [p. 13]. Festo publishes its manuals
at www.festo.com/sp. Page numbers in brackets are from this manual.

Also read on 2026-11-08, for differences only: the *CMMT-AS-...-S3* manual (document 8259151,
version 2026-06b) and the *CMMT-ST* manual (document 8259159, version 2026-06o; the
CMMT-ST-...-MP-S0, same firmware version [ST p. 12]). Their CiA 402 text matches the S1:
the same standard objects, modes, homing methods, sync range and PDO size (S3 pp. 282, 342,
865, 875; ST pp. 234, 292, 538, 548). The differences are at the end of this page.

The CMMT is a multi-protocol drive: EtherCAT with CiA 402, PROFINET with PROFIdrive, or
EtherNet/IP / Modbus TCP. Switches behind the front panel pick the protocol, or leave the choice
to a parameter. A change takes effect only after a restart [pp. 243–244]. This page covers
EtherCAT with CiA 402.

## Who may command the drive

- **The commissioning plug-in can take master control away from the fieldbus at any time**,
  even during a move. Taking it or giving it back makes the drive do a category 1 stop. While
  the plug-in holds control, the fieldbus cannot start motion [pp. 132–133]. Statusword bit 9
  (remote) shows whether the CiA 402 interface has master control [p. 633]. Parameters can be
  written without master control [p. 133]; the abort list still has a code for it, 0x08000021
  [p. 643].
- **Enabling needs the hardware input as well as the controlword.** Px.10232 (0x218E:02)
  picks the enable source. With "I/O and fieldbus" the CTRL-EN input must already be high and
  then the controlword must give a fresh rising edge. A new edge on CTRL-EN alone does not
  enable the drive [pp. 313–316]. The manual gives no factory value for Px.10232. "I/O or
  fieldbus" (5) switches off when either source drops [p. 316].

## State machine

- **0x000F in Ready to switch on goes on to Operation enabled by itself** (T3 and T4)
  [p. 631].
- **There is no 0x605A, 0x605B, 0x605C, 0x605D or 0x605E.** The option-code objects are not
  in the object list [pp. 649–652]. The stop behaviour is fixed or set through Festo's stop
  categories: removing the enable gives a category 1 stop (ramp, brake, then power stage off)
  [p. 322]. Errors stop with category 0, 1 or 2, chosen per diagnostic message [p. 513].
- **Quick stop ramps with 0x6085** and clears statusword bit 5 [p. 324]. The command table
  lists T16 (Enable operation from Quick stop active) [p. 631]. The manual does not say whether
  the drive stays in Quick stop active or goes on to Switch on disabled: check it on the drive.
- **Halt (bit 8) is ignored in CSP, CSV, CST and jog.** In PP, PV and PT it brakes with the
  mode's own deceleration and continues when cleared. In homing it aborts the homing for good
  [pp. 325–326, 632].
- **Statusword bit 8 is "drive is moving" and bit 15 is "drive is referenced"**, both
  manufacturer-specific [p. 633]. Bit 11 (internal limit active) also comes on for
  speed, current and voltage limits, software and hardware limit switches, stroke limits and a
  direction lock [p. 634].

## Modes of operation

- **Modes 1, 3, 4, 6, 8, 9 and 10, plus 0 (a Festo variant of profile position), −3 (profile
  jog) and −20 (record table)** [pp. 270–271]. No vl (2) and no IP (7). Profile jog uses
  controlword bits 4/5 for positive/negative and 11/12 for slow/fast [p. 632].
- **PP needs a valid homing.** Its precondition includes statusword bit 15 [pp. 273, 275].
  Velocity, torque and jog commands do not [p. 327].
- **Switching between CSP, CSV and CST on the fly works only if 0x6060, 0x6061 and the
  setpoints of both modes are in the PDOs** [p. 270]. Leaving a cyclic mode for PP, PV, PT or
  homing needs a stop first; going from a profile mode into a cyclic one needs the move to
  finish or be stopped [p. 270].
- **0x60B1 and 0x60B2 in CSP are used only if the interpolation mode Px.11412 says so**
  (CSP-V, CSP-T or CSP-VT). In plain CSP the drive makes its own feed-forward [p. 295].
- **Torque objects refer to the gear output shaft by default**, not the motor shaft. The manual
  names this as a deviation from CiA 402. Px.128062 (0x2195:08) switches 0x6071, 0x6072, 0x6074,
  0x6077, 0x60B2, 0x60E0 and 0x60E1 to the motor side; it needs a re-initialisation
  [pp. 289, 635].
- **0x6075 and 0x6076 are both mapped to the same parameter**, the motor's nominal current
  (Px.7118) [p. 650]. Do not read 0x6076 as a rated torque.

## Units and scaling

- **There is no 0x608F, 0x6091 or 0x6092.** Gear ratio and feed constant are 0x60E8/0x60ED and
  0x60E9/0x60EE [p. 652]. Their names in the object list cross over (a "denominator" under
  0x60E8): check them against the ESI.
- **Units are set with 0x60A8–0x60AB**: an SI unit plus a power-of-ten prefix. One unit
  family covers position, velocity, acceleration and jerk; scaling is in powers of ten only
  [pp. 149–155]. The factory unit is revolutions: position in 0.001 rev, velocity in rpm,
  acceleration in rpm/s [pp. 148, 152–153].
- **Changing the unit over the fieldbus changes it for the whole drive.** It can be changed
  only in Pre-Op and takes effect after a re-initialisation, which converts every stored
  parameter [p. 147]. The resolution objects 0x2194:01–04 also take effect only after a
  re-initialisation [p. 150].
- **"CiA 402 increments" (SI numerator 0xC5) gives a power-of-two count per motor revolution**,
  independent of the user unit [pp. 149–152]. The printed range of the exponent is garbled;
  read it as 2¹² to 2³⁰ and check on the drive.
- **A master's own scaling must match the drive's prefix.** The manual's CODESYS examples set
  the axis increments to 100 000 for 10⁻⁵ rev and to 1 000 000 for µm [pp. 155–156].

## PDO mapping

- **One free RxPDO (0x1600) and one free TxPDO (0x1A00)**, up to 16 entries each, mapped in
  Pre-Op [pp. 636–638]. Two more TxPDOs are fixed: 0x1AF0 carries the "new diagnostic message"
  flag (0x10F3:04) and 0x1AF1 the DC time stamp (0x10F8) [pp. 638–639].
- **The default RxPDO carries every mode's setpoints**: 0x6040, 0x6060, 0x607A, 0x6081,
  0x60FF, 0x6071, 0x60B1, 0x60B2, plus 8 bits of padding. The default TxPDO is 0x6041, 0x6061,
  0x6064, 0x606C, 0x6077 and padding [pp. 636–638].
- **An SDO write to an object mapped in the RxPDO is refused** (abort 0x06010006) [pp. 641,
  643]. Write 0x6060 either by PDO or by SDO, not both.
- **The cycle is 1 to 20 ms, in whole milliseconds.** Free run, SM-synchronous or DC SYNC0;
  a cycle that is not a whole number of ms raises "Invalid cycle time" [pp. 626–628]. There is
  no 0x60C2.

## Homing

- **Methods −27, −23, −18, −17, −2, −1, 1, 2, 7, 11, 17, 18, 23, 27, 33, 34 and 37.**
  The factory default is 37. There is no 35, and none of 3–6, 8–10, 12–14, 19–22 or 24–26
  [p. 330].
- **The negative methods**: −17/−18 home on a fixed stop (block), −1/−2 on a fixed stop then
  the index pulse, −23/−27 on a fixed stop or limit switch then the reference switch. The stop
  detection uses a current threshold and a time window (Px.8414, Px.8415) [pp. 335, 340–342].
- **The 7/11/23/27 reference-switch methods reverse when they hit a fixed stop** in the search
  direction [pp. 338–339]. The limit-switch methods need
  hardware limit monitoring switched on (Px.101116) [p. 336].
- **0x607C is the axis zero offset: axis zero = reference mark + 0x607C** [p. 344]. With
  Px.841 the drive then moves to the axis zero by itself [p. 328].
- **Method 37 is the only one that runs without controller enable** [p. 326]. The CiA 402
  section says all methods need Operation enabled [p. 344]; the two pages disagree.
- **Bit 8 (halt) with bit 4 aborts homing**, with the deceleration in 0x609A [p. 344]. The
  abort leaves bits 10 = 1, 12 = 0, 13 = 0 [p. 345].
- **The homing speeds are 0x6099:01/02 and the acceleration 0x609A**; jerk, the search limits
  and the move to axis zero have only Festo objects (0x2172) [p. 343].

## Errors

- **0x603F is named "Severest Diagnosis ID"**: the 16-bit form of the worst active error. The
  full 32-bit Festo diagnosis number is in 0x210D:08 [pp. 513, 517]. The manual is unclear
  whether 0x603F holds the CiA emergency code or the low 16 bits of the Festo number. Read both
  once with a known fault.
- **One emergency code covers many Festo messages**: 0x2081, for example, stands for eight
  different current errors [pp. 644–645]. Read the diagnosis number to know which one.
- **An error is reset only after its cause has gone**; an emergency with code 0x0000 confirms
  the reset [pp. 515, 644].

## Modulo axes

Modulo is on as soon as either limit in 0x607B is not 0. In PP, 0x60F2 bits 6–7 choose
normal, negative-only, positive-only or shortest-path moves [p. 487]. 0x6064 then reads the
position inside the modulo range [p. 488].

## Where the S3 and ST differ

- **CMMT-AS-...-S3** adds the extended safety sub-functions (STO, SS1, SS2, SOS, SLS and more).
  Its safe fieldbus is **PROFIsafe over PROFINET only**: the manual describes no FSoE, so on
  EtherCAT the safety functions come from the safety inputs [S3 pp. 521, 539–541]. The CiA 402
  objects are the same as on the S1. Safety behaviour belongs to `../safety-boundary.md`.
- **CMMT-ST** drives stepper and EC motors [ST pp. 74, 164]. It has no second encoder channel
  (no 0x60E4:02, 0x60E5:02), no analogue setpoint input, no master-slave coupling and no CDSB
  operator unit; it adds field weakening [ST pp. 436, 564]. The CiA 402 behaviour above
  applies unchanged.
