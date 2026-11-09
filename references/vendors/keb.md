# KEB COMBIVERT F6 / S6

**Read 2026-11-08**: KEB Automation KG, *COMBIVERT F6/S6 Programming Manual | Control,
Application / Compact / Pro – V3.0*, document 20294260 EN 00, software version 3.0 (© 2022).
KEB publishes its manuals through the document search at https://www.keb.de. Page numbers in
brackets are the `=== page N ===` markers of the text extract. They match the PDF page and the
printed page number.

The manual covers the F6 inverter and the S6 servo drive with the Compact (K), Application (A)
and Pro (P) control boards, software 3.0 [p. 17]. It is the drive-function manual. **EtherCAT
details (PDO mapping, sync managers, watchdog) are in a separate *Programming manual | Fieldbus
systems*,** which needs a KEB login and was not read [pp. 72, 490, 493].

## KEB parameters behind the profile objects

KEB's own dictionary is the real one. Most CiA 402 objects are second addresses for a KEB
parameter in groups such as co (control), st (status), ps (positioning), hm (homing), cs
(torque limits) and vl (velocity mode) [pp. 489–491]. A few examples: 0x6040 = co00 (KEB's
0x2500), 0x6041 = st00 (0x2100), 0x6060 = co01 (0x2501), 0x607A = co19, 0x60FF = co16,
0x6098 = hm01 (0x3101), 0x607C = hm00, 0x6072/0x60E0/0x60E1 = cs12/cs13/cs14 [pp. 490–491].
Writing either address changes the same value. **Manuals, COMBIVIS and KEB support name the KEB
parameter, not the CiA index**, so keep this mapping to hand.

Some objects only partly match a KEB parameter. 0x605B, 0x605C and 0x605E write bits in KEB's
co32 *state machine properties* (0x2520), and 0x60C2 writes fb10, the sync interval in µs
[pp. 491–492].

## Identity

- **0x1018:02 product code is 0x00800000 for every F6/S6 on EtherCAT/CANopen.** The revision
  (0x1018:03) is the COMBIVIS parameter-description ID, and 0x1018:04 is the drive serial
  number [p. 492]. The product code does not tell an F6 from an S6, or one control board from
  another.
- **0x6502 reads 0x000001A3: PP, VL, HM, CSP, CSV.** CST is not in it, though co01 accepts 10
  and the manual documents CST [pp. 126, 172, 492]. It is unclear whether 0x6502 is just out
  of date. Check on the drive before you rely on CST.

## State machine

- **KEB adds states of its own**, shown in st12 (KEB's 0x210C), not in the statusword: *Start
  operation active* (flux build-up, rotor position detection, brake opening) between Switched
  on and Operation enabled, *Mod off pause* / *protection time active*, *Shutdown* and *Disable
  operation active*, *Power off* and *Suppressed error* [pp. 20–23, 27–28].
- **Enable operation can be delayed by a minimum modulation-off time.** If 0x000F arrives
  while the time runs, the drive waits in *Mod off pause active* and goes on by itself when the
  time ends [pp. 21, 102]. After OC, OP, OP2 or OL2 there is a protection time; six of these
  errors within two minutes block the drive for 2 minutes [p. 102]. In the "endless" variant
  only a 24 V or mains power cycle clears it [p. 102]. A master with a short enable timeout
  sees this as a failed T4.
- **co32 bit 3 can make T4 edge-triggered** (a rising edge on bit 3, not its level). co32 bit 13
  decides whether an edge sent during the off time counts [p. 29].
- **Quick stop is off unless co32 bit 9 is set.** Without it, controlword bit 2 is ignored and
  no quick stop happens, not even one that an error reaction or limit switch asks for
  [pp. 22, 29, 43, 85, 113]. The default of co32 is not given in the pages read. Quick stop can
  start only from Operation enabled [p. 113].
- **Clearing bit 1 (enable voltage) always switches modulation off at once** [p. 23].
- **The controlword the drive acts on can differ from 0x6040.** co30 masks which bits come from
  the bus (default 0xFFFF = all), digital inputs can set bits via co28/co29, and error
  reactions clear bits 0, 2 or 3 internally. st14 (KEB's 0x210E) shows the controlword that
  results [pp. 24–25, 42].
- **Bit 15 opens the brake** when co21 brake mode = 0 (manufacturer-specific). With co21 = 1 the
  state machine drives the brake, and with co21 bit 5 set it waits for the brake to open or
  close before it enters or leaves Operation enabled [pp. 24, 32, 35]. KEB recommends mode 1
  with the wait for most applications [p. 33]. The default of co21 is not given in the pages
  read.
- **Halt (bit 8) is supported only in VL, HM and PP** [p. 24]. 0x605D is not mentioned anywhere.
- **Statusword**: bit 8 = synchronous to the fieldbus, bit 9 (remote) not supported, bit 14 =
  Power off or suppressed error active, bit 15 = brake state [p. 26]. Bit 7 (warning) is set
  only for warnings enabled in pn28 [pp. 26, 44].
- Whether 0x000F in Ready to switch on does T3 + T4 is not stated.

## Option codes

KEB uses **negative (manufacturer-specific) values for every ramped stop**. Of the profile's
codes it keeps only 0, and, for 0x605B/0x605C, 1.

| Object | F6/S6 values | Differs from the profile |
|---|---|---|
| 0x605A quick stop | 0; −1 to −6 | **no 1–8.** 0 switches off and goes to **Switched on**. −1/−2 fault-reaction ramp (pn), −3/−4 standard ramp (co), −5/−6 positioning ramp (ps); −3/−5 then Switched on, −2/−4/−6 stay in Quick stop active, −1 end state not stated |
| 0x605B shutdown | −1, 0, 1 | −1 = fault-reaction ramp, 1 = standard ramp |
| 0x605C disable operation | −1, 0, 1 | as 0x605B |
| 0x605E fault reaction | −1, 0 | −1 = fault-reaction ramp; no 1–4 |
| 0x605D halt | not mentioned | — |

[pp. 113, 491]. **Code ported from another drive that writes 0x605A = 2 or 6 is refused or
does something else here.** The equivalent of 6 is −2, −4 or −6, depending on which ramp you
want. 0x605A = 0, −3 and −5 end in **Switched on**, not Switch on disabled as in the profile
(T12) [p. 113]. The manual does not say what controlword brings the drive back from there.
Watch the statusword rather than assuming the profile's 0x0006 → 0x0007 → 0x000F path. The manual gives no
defaults for these objects.

In the cyclic modes, quick stop ignores the master's set-points and the drive makes its own
ramp. If quick stop is cancelled mid-ramp, the cyclic set-point applies again at once [p. 113].
Ramps are KEB parameter sets in s⁻² and s⁻³ (fault reaction pn45–pn62, standard co48–co60,
positioning ps48–ps59) [pp. 29, 45, 145]. 0x6085 is not mentioned.

## Error reactions

Each configurable error has its own reaction parameter (pn04 … pn89): fault, ramp then fault,
quick stop, disable operation, shutdown, warning, ignore, and auto-retry versions [pp. 41–44].
**Reactions 3 and 4 (disable operation, shutdown) clear the bit internally and set it again by
themselves when the cause goes away.** With bit 3 or bit 0 still set in 0x6040, the drive
starts again without any command from the master. KEB warns against this outside special
cases [pp. 42–44]. With co32 bit 2 = 0 the fault reaction is always immediate: the pn ramps
are not used and the motor coasts [p. 43].

The fieldbus watchdog is pn21 (0 = off) with its reaction in pn22. Details are in the Fieldbus
manual [p. 72]. The pn22 default in the table on p. 41 appears to be in the warning/ignore
column, but the extract's columns are hard to align. Treat it as unverified and set pn21/pn22
yourself.

## Modes of operation

- **co01/0x6060: −2 jog (KEB), 1, 2, 6, 8, 9, 10.** 3, 4, 5 and 7 are reserved: **no PV, PT or
  IP** [p. 126]. 0 means "no mode change", not "no mode" [p. 126].
- **Jog (−2)** is driven from digital inputs. Selected by an input (cm34), it resets errors once
  and runs the state machine up to Operation enabled by itself. In jog mode the fieldbus
  watchdog and heartbeat errors are off, and limit-switch errors are suppressed (the switches
  still stop the axis) [pp. 178–179].
- **A mode change is allowed while running.** On entry to CSP, CSV or CST, bit 4 of
  co10/co11/co12 picks whether the interpolator starts from actual values (default) or from
  set-points the master filled in beforehand. Enter CSP at standstill unless you pre-fill
  [pp. 166, 186].
- **The position controller is on in PP and CSP and off in VL, CSV, CST and jog**, set by ps00 =
  auto. ps00 = 2 forces it on [p. 418].

## Profile position

- **Set-points queue in a five-entry FIFO.** Bit 12 stays set while the FIFO is full [pp. 128,
  130]. **Bit 9 (change on set-point) is not supported** [p. 127].
- **Target reached needs bit 4 low** when the target is reached [p. 140]. With end velocity
  0x6082 ≠ 0 it is set when the profile ends, ignoring the window [p. 140].
- **A target outside the software limits 0x607D (ps16/ps17) is simply not moved to, with no
  error or warning** [p. 416].
- **0x607B (ps18/ps19) is a modulo range** that wraps st33 and st37 only [p. 417]. Rotary
  direction comes from KEB's ps33, not 0x60F2 [p. 133]. A KEB index mode of up to 32 stored
  positions sits under PP (ps38) [pp. 127, 131].

## Velocity mode (VL)

0x6042 is in 1 rpm. KEB's vl21 adds 1/8192 rpm resolution [p. 143]. **Controlword bits 4–6
and 8 (ramp enable/unlock/reference, halt) act only when co32 bit 8 is set**, for
compatibility with software before 2.2 [p. 144]. 0x6044 is in 1 rpm [p. 493].

## Homing

- **Methods 1–14, 17–30, 33, 34, and 37 (with 35 as its alias).** The default is **37**,
  which sets the position without moving [pp. 151, 154–158]. **No negative methods** are
  described. The manual says the mode follows IEC 61800-7-200 [p. 151].
- **The manual contradicts itself on limit switches in homing.** The homing chapter says they
  are always active in drive-side homing [p. 154]. The limit-switch chapter says homing mode is
  excluded from the limit-switch protection at the factory (hm15), and marks the hm15 homing bit
  "not available" [p. 86]. A plausible reading: the switches serve as homing inputs, but their
  stop reaction does not fire. Verify on the drive. **Limit-switch inputs are
  active-low; the home switch is active-high.** If no input is assigned but a reaction is set,
  the limit-switch reaction fires at once [pp. 85, 153].
- **The home offset is stored non-volatile in hm09**, so with a single-turn absolute encoder the
  position survives a power cycle if the axis did not move. hm09 can also be written directly
  to reference without homing mode [p. 153]. KEB's "homing done" flag is still 0 after power-on.
  Changing co03, co04 or co08 clears it [p. 159].
- hm22 shifts the index pulse in software, so it can be about half a revolution from the switch
  edge [p. 158].

## Units and scaling

- **No factor group is described.** 0x608F, 0x6091 and 0x6092 do not appear in the pages read.
  **Position = co03 bits per revolution of the position encoder, default 16 (65536 inc/rev)**.
  Its range is ±2^(31 − co03) revolutions [p. 416]. A gear between position encoder and motor
  is ps35/ps36 [p. 421].
- **Velocity (0x60FF, 0x60B1, 0x606B, 0x606C, 0x6080) is in rpm / 2^n**, set by co02:
  co02 = 0 gives 1/8192 rpm, 13 gives 1 rpm [pp. 169–170, 175]. The default of co02 is not given in
  the pages read.
- **Torque 0x6071, 0x60B2 and 0x6077 are in 0.1 % of rated torque by default**, finer with co84
  (down to 0.01 %). The limits 0x6072, 0x60E0 and 0x60E1 stay at 0.1 % [p. 174]. 0x60B2 acts
  only with cs21 = 2 [p. 403].
- **0x60E0/0x60E1 do not have the profile's quadrant meaning by default.** cs13/cs14 are the
  *motoring* limits for positive and negative speed. The generating limits are cs15/cs16.
  For the profile's behaviour set cs15 = −2 and cs16 = −2 [p. 185].
- **0x6083 is co48 in inc/s²**, inc/rev from co03 [p. 145]. KEB's own ramps are in s⁻²
  (0.01 s⁻²) [p. 145].
- **0x6080 caps speed in CST**: above it the drive switches to speed control, and bit 12 drops
  [p. 175].

## Cyclic modes and synchronisation

- **0x60C2 maps to fb10 (µs)**. fb10 is set automatically from the first measured sync interval
  after power-on. If written later it must match the EtherCAT register, or the drive does not
  synchronise [pp. 187, 492]. Statusword bit 8 shows sync. After power-on the synchronous mode
  is off until it is reached [p. 187]. Maximum cycle is 16 ms [p. 187].
- **The interpolators add delay**: cycle × (points − 1), e.g. 3 ms for a 4-point B-spline at
  1 ms. CSP needs at least 4 points to derive feed-forward [pp. 165–166, 170]. co13 can shift
  the position to make up for it [p. 166]. Changing co10 to linear during motion leaves a stale
  feed-forward [p. 165].

## Software and hardware limits

The software limits exist twice. 0x607D (ps16/ps17) is checked at the start of a PP move
[p. 416]. KEB's pn18/pn19 trigger the pn20 reaction when crossed [p. 85]. Both positive and
negative limit switches active together always faults [p. 87]. If a limit-switch reaction is
quick stop and co32 bit 9 is off, nothing happens [p. 85].

## Touch probe

Touch probe 1 only (0x60B8 = hm10, 0x60B9 = hm11, stored in hm12/hm13). Sources: input I1, the
position encoder's index, or via 0x60D0 inputs I1–I4 or the index [pp. 159–160]. It works in
every mode [p. 159]. With the index as source, hm12/hm13 hold the forward and reverse
directions rather than rising and falling edges [p. 159].

## PDO mapping

Not read: the manual sends EtherCAT mapping to the Fieldbus manual [p. 490]. It says only
that F6/S6 are certified EtherCAT slaves and that the mapping objects sit in KEB's pr group
[p. 490].
