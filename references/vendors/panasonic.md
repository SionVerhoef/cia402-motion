# Panasonic MINAS A6BN (EtherCAT, linear gantry control type)

**Read 2026-11-08**: Panasonic Industry Co., Ltd., *Technical Reference – EtherCAT Communication
Specification –* for the MINAS A6BN series, document No. SX-DSV03736, revision R2.1 (Aug. 8,
2024). Panasonic publishes MINAS manuals on its industrial-device download pages
(https://industry.panasonic.com); the document itself says to ask the seller [p. 1]. Page numbers
in brackets are **PDF pages**; the printed page number is 9 lower. The English text is an
unofficial translation and only the Japanese original is binding [p. 2].

**Which products this covers.** The A6BN is the *gantry control type* of the MINAS A6B family,
for linear motors only [pp. 1, 14]. The document applies to CPU1 and CPU2 software Ver.3.20 and
manufacturer software Ver.1.00 [p. 11]. It was derived from the A6BL (standard type) document
[p. 3], and its comparison table sets the A6BN apart from the A6BL and A6BM [pp. 20–22]. **The
standard rotary MINAS A6B is a different document and may differ anywhere on this page.** The
text is written in rotary terms; for a linear motor read r/min as mm/s, torque as thrust and
inertia as mass [p. 14].

## Modes of operation

- **Supported: pv (3), tq (4), hm (6), csp (8), csv (9), cst (10)** [pp. 93–95]. vl and ip are
  not supported; 6060h = 7 must not be written [pp. 11, 138].
- **pp (1) is accepted but not supported on the gantry type**: settings can be made, operation
  is not guaranteed [pp. 11, 27, 93]. 0x6502 still reports pp as supported [p. 93]. Do not port a
  pp-based axis to this drive.
- **0x6060 is 0 after power-on.** Enabling operation with 6060h and 6061h both 0 raises Err88.1;
  so does writing an unsupported mode [pp. 94, 96, 295]. Writing 0 after a valid mode keeps the
  last mode [p. 94].
- **Mode changes only at standstill.** The switch takes about 2 ms, during which 6061h and the
  mode's TxPDO objects are not valid. A change while moving, homing or decelerating is not
  guaranteed and can raise Err27.4 [p. 96].
- **pv, pp and tq need a cycle of at least 250 µs** [pp. 27, 176]. Jerk (0x60A3/0x60A4/0x6086)
  is not supported [p. 254]; 0x6082 end velocity always reads 0 [p. 100].

## State machine

- **0x000F in Ready to switch on does T3 + T4**, straight to Operation enabled [p. 88]. The
  document still tells the master to wait for each state in 0x6041 before the next command
  [p. 87].
- **Switched on needs main power.** Without it the drive stays in Ready to switch on; an STO
  input forces Switch on disabled [p. 86].
- **Servo-on waits for magnet-pole estimation** when that method is configured [p. 86].
- **Wait about 100 ms after reaching Operation enabled before sending motion commands**
  [pp. 86, 134, 148].
- **An ESM state change requested while in Operation enabled or Quick stop active raises
  Err88.2** [p. 293].
- **Controlword bit 11 is Panasonic's "disable correction"**: it switches off the gantry
  cross-axis corrections (mass ratio, feed-forward and vibration corrections that look at other
  axes) [p. 89]. Bits 12–15 are unused [pp. 88, 131].
- **Statusword bits 8, 14 and 15 are always 0** [pp. 91–92]. Bit 9 (remote) is 1 once the ESM
  is PreOP or higher [p. 91]. **Bit 11 (internal limit active)** is set by a torque limit,
  POT/NOT, the software limit or a speed limit; with a torque limit of 0 it stays 1 even with the
  servo off [p. 92].
- **Halt in homing does not resume**: clearing bit 8 after a halt stops the homing for good
  [p. 88].
- PANATERM test runs with 3799h bit 0 = 1 run while EtherCAT is up, but the drive is then not in
  Operation enabled and quick stop does not act [p. 19].

## Option codes and stopping

| Object | A6BN allows | Differs from the profile |
|---|---|---|
| 0x605A quick stop | −2, −1 (vendor), 0, 1, 2, 3, 5, 6, 7 | 0 = Panasonic's servo-off sequence (3506h) |
| 0x605B shutdown | 0, 1 | **0 = the servo-off sequence 3506h**, not a plain coast |
| 0x605C disable operation | 0, 1 | 0 = the servo-off sequence 3506h |
| 0x605D halt | 1, 2, 3 | **no 0**; 3 = max torque with 60C6h |
| 0x605E fault reaction | 0, 1, 2 | **applies only to EtherCAT alarms** (Err80, 81, 85, 88) |
| 0x6007 abort connection | 0–3 | **reaction to main-power loss, not to a lost connection** |

[pp. 130, 225–236]. The shipment values are in the separate standard specification
(SX-DSV03740) [pp. 14, 225], which was not read, so no defaults are given here.

- **Ramp sources depend on the mode.** In hm the "profile deceleration" codes use 609Ah; in tq
  and cst every ramp code uses the torque slope 6087h, and 3/7 mean an immediate zero torque
  [pp. 230, 232, 234–236].
- **Every other alarm stops by 3510h** (Panasonic's alarm sequence), whatever 605Eh says
  [p. 236]. Panasonic's own stop sequences outrank the CiA 402 ones when several stop causes
  overlap [p. 226].
- **6007h decides what happens when the main supply drops** while enabled; Panasonic's 3507h to
  3509h take over after a delay, and 3509h = 2000 disables that takeover [pp. 227–229]. A lost
  EtherCAT connection is handled by the PDO watchdog (Err80.4) and 605Eh instead [pp. 16, 279].
- **"Stopped" means below about 30 r/min** in every stop sequence [pp. 229, 231].
- POT/NOT behaviour is set by Panasonic's 3504h/3505h; 3504h = 1 stops with 6085h (or 6087h in
  torque modes) [p. 237]. **0x607E polarity also swaps POT and NOT**: POT is always the positive
  command direction [pp. 22, 249–250].

## Homing

- **Methods 1–14, 17–30, 33, 34, 35, 37 and −1 to −4** (0x60E3 lists 36 entries) [pp. 143, 147].
- **35 and 37 are the same**; Panasonic recommends 37 for new designs. They run outside
  Operation enabled, but need 100 ms with no command change first and are not guaranteed with the
  servo off or the motor moving [p. 165]. All other methods started outside Operation enabled give
  a homing error [p. 151].
- **Negative methods home on a hard stop**, detected when torque demand sits at the limit 5350h
  for 5351h ms with speed under 5352h (all Panasonic objects; 5352h = 0 drops the speed test)
  [pp. 144, 166–167]:

  | Method | Search |
  |---|---|
  | −1 | hard stop, positive, no index |
  | −2 | hard stop, negative, no index |
  | −3 | hard stop, negative, then reverse to the first index pulse |
  | −4 | hard stop, positive, then reverse to the first index pulse |

  [p. 143]. The direction for each number comes from the method table; the diagrams on
  pp. 166–167 could not be checked in the text. Err24.0 (following error) may trip before the
  stop is detected; set 5350h and 3014h together [pp. 166–167].
- **With an absolute scale, homing is an error** and homing attained (bit 12) is always 1
  [pp. 146, 151]. With an incremental scale, home before any positioning [p. 139].
- **Switch edges must come in on the latch inputs**: HOME, POT and NOT on SI5, SI6, SI7, or the
  homing fails [pp. 148, 151].
- **Halting between home detection and completion raises Err27.7** [p. 149]. 6064h and 60F4h are
  undefined in that window [p. 148].
- **A second start-homing edge during homing is ignored**, and the method cannot change mid-run
  [pp. 142–143]. With Panasonic's 3698h bit 8 = 1, switching 6060h from csp to hm with bit 4
  already set starts homing (csp only) [p. 142].
- 0x6098 is listed as not PDO-mappable on p. 143 but as RxPDO in the dictionary list [p. 335].

## Units and scaling

- **Position in command units, velocity in command units/s, acceleration in units/s²**; torque
  objects in 0.1 % [p. 99]. **0x6080 max motor speed is in r/min** (mm/s for a linear motor, by
  the p. 14 rule) [pp. 99–100]. 0x6076 is in mN·m [p. 105].
- **0x608F is set by the drive**: linear type 1 000 000 increments per "revolution" of
  (scale resolution in nm/p) [pp. 244, 248]. The factory 0x6092 gives a 1:1 gear only with a
  1 nm/p scale [p. 244].
- **The electronic gear must stay within 8000:1 to 1:1000.** Outside it, or if an intermediate
  value overflows, the drive raises Err88.3, which cannot be cleared: fix the gear and power-cycle
  [pp. 244, 296]. A 125 µs cycle works only with a 1:1 gear [p. 245].
- **New 0x6091, 0x6092, 0x607C and 0x607E values take effect only at Init → PreOP**, at power-on,
  at homing completion or after some PANATERM actions [pp. 244, 250, 253, 335]. Writing them in OP
  changes nothing until then.
- **0x607E accepts only 0 or 224** (all three polarities together) [p. 249].
- **0x607B is fixed** at 80000000h / 7FFFFFFFh internally; writes have no effect [pp. 22, 252].
- **The software limit 0x607D** works in pp/csp only after the position is known (absolute scale:
  PreOP; incremental: after homing, and lost again at Init → PreOP). Outside the range the axis
  can only move back inward. A position wrap with the limit active raises Err88.3 [pp. 102–103].
- **0x60E0/0x60E1 act only when Panasonic's 3521h = 5** [p. 101].

## PDO mapping

- **Free mapping: 0x1600–0x1603 and 0x1A00–0x1A03**, up to 32 entries each, **at most 32 bytes
  per direction**; more raises Err85.0/85.1 [pp. 27, 49, 289–290].
- **Change mapping only in PreOP, with sub-index 0 written to 0 first**; otherwise abort
  0x06010003. It takes effect at PreOP → SafeOP [pp. 63–64]. Do not map the same object twice
  [p. 64].
- **The default assignment is 0x1600/0x1A00, a csp set with touch probe** (controlword, 6060h,
  607Ah, 60B8h; statusword, 603Fh, 6061h, 6064h, 60B9h, 60BAh, 60F4h, 60FDh). 0x1601–0x1603 are
  ready-made sets for mixed modes and torque limits [pp. 66–67].
- **An SDO write to an object that is also in a PDO is overwritten** by the PDO [pp. 41, 48].
- **Mapping and other object changes are lost at power-off** unless saved with 1010h:01 =
  "save" (65766173h); saving takes up to about 10 s and blocks other SDOs [pp. 68, 81].
- Complete access is not supported [p. 27]. **Sending the same mailbox counter twice stops SDO
  handling** until the next Init → PreOP [p. 43].

## Synchronisation and timing

- **DC, SM2 and free run** [p. 37]. 1C32h:01 is rewritten at PreOP → SafeOP to match the DC
  activation register, so the ESC setting wins [p. 70]. 0x60C2 is set from the cycle time; do not
  write it [p. 255].
- **Cycle times are stated inconsistently.** The sync-manager pages list 250 µs to 10 ms [pp. 70–
  71]; the specification list and DC table add 125 µs [pp. 27, 74]; the Err81.0 page lists only
  250 µs to 4 ms [p. 283]. Check the cycle against the drive's ESI and software version.
- **Output shift is not supported; input shift (1C33h:03) is 0–3.875 ms in 125 µs steps**
  [pp. 70, 75]. Free run: no PDO faster than 250 µs [p. 40].
- **Only the RxPDO watchdog (SM2) is checked**, so Err80.4 trips only in OP [p. 279]. The
  watchdog time must be at least two cycles (2 ms in free run) or Err81.4 refuses SafeOP
  [p. 285].
- **Lost-link detection (3743h) is off by default.** Only the slave that sees the broken port
  alarms; later slaves need the PDO watchdog [p. 291].
- **csp estimates a missed target** after a communication error and corrects the command
  [p. 135]. Panasonic's 3722h bit 5 limits the
  position step per cycle by 0x6080 to avoid Err27.4; with that bit set and 6080h = 0 the axis
  does not move and bit 11 stays 0 [p. 136].

## Faults

- **Clearing an EtherCAT alarm takes two steps**: set Error Ind Ack (AL Control bit 4), then
  controlword bit 7. A clear cannot happen in Fault reaction active, nor while the external A-CLR
  input is on [p. 298].
- **0x603F carries only the main alarm number**, as FF00h + number; the sub-number is not
  readable there, and 603Fh updates after statusword bit 3 [p. 297]. Panasonic's 4F37h gives
  main and sub-numbers [pp. 263–265].
- **Panasonic's 4F33h reports why the motor is not moving** (no servo-ready, no enable, POT/NOT,
  low torque or speed limit, and so on) [p. 262].

## Touch probe

- **Two probes**: EXT1 (must be on SI5) or the scale's Z phase for probe 1, EXT2 (on SI6) or Z
  for probe 2. Selecting EXT without the input assigned raises Err88.3 [pp. 215–216, 296].
- **No falling edge on Z**, and Z with an absolute scale raises Err88.3 [pp. 215, 218].
- **Trigger pulses need at least 2 ms on and 2 ms off** [p. 215].
- **Settings are read on the 0 → 1 edge of bit 0/8**; to change them, stop and restart the probe
  [p. 221]. **Entering hm or ESM Init switches the probe off** and clears 60B9h [p. 215].
- Status bits 1/2/9/10 toggle on each latch instead of staying set when Panasonic's 3697h
  bit 13 = 1 [pp. 219, 223]. Latch delay correction: 3709h/3792h in 25 ns [p. 224].
