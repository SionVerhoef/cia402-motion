# Leadshine EL8-EC servo drives and EM3E EtherCAT stepper drives

**Read 2026-11-08**: Leadshine Technology Co., Ltd., *EL8-EC Series AC Servo Drive User
Manual*, V2.01 (running header "V2.0.1"; no date printed) [EL8]; and Leadshine, *EM3E Series
EtherCAT Stepper Drive User Manual*, for EM3E-522E, EM3E-556E and EM3E-870E, V1.2 dated
06/01/2020 in its revision record ("add debug port, change ESI file") [EM3E p. 2]. Leadshine
publishes its manuals at https://www.leadshine.com. Page numbers in brackets are PDF pages; in
the EM3E manual the printed page number is the PDF page minus 6.

Two products, two manuals: say which one a claim comes from. **EL8-EC** is an AC servo drive
(450 W to 2 kW) [EL8 p. 11]. **EM3E** is a stepper drive for 20–50 VDC [EM3E p. 7]. Neither manual names a firmware version. On the EL8 the versions are
in P11.00–P11.02 (0x27A9:01–03) [EL8 p. 120]; on the EM3E in 0x3100:01–03 [EM3E p. 22]. Most
EL8 parameters Pcc.nn are also objects, mostly at 0x2000 + 0x100 × cc + nn (P00.06 = 0x2006,
P05.13 = 0x2513), but the higher classes break that pattern (P0D.02 = 0x27A5:03) [EL8 pp.
62–65, 73].

**The EL8 manual contradicts itself on defaults.** The summary table and the per-object pages
disagree for 0x6065, 0x6067, 0x6068, 0x6080, 0x6085 and 0x6092:01, among others [EL8 pp.
68–69 vs. 125–131]. Read the value from the drive before relying on any default.

## Which drive does what

- **EL8-EC: modes 1, 3, 4, 6, 8, 9, 10** (PP, PV, PT, HM, CSP, CSV, CST); no ip, no vl. 0x6060
  defaults to 8 [EL8 pp. 125, 179].
- **EM3E: modes 1, 3, 6, 8 only** (PP, PV, HM, CSP); 0x6502 = 165. No torque modes, no CSV.
  0x6060 defaults to 8 [EM3E pp. 7, 27, 29]. An unsupported mode raises error
  0x5201 [EM3E p. 30].
- **The EM3E identifies itself under an older name**: 0x1008 reads "DM3C-EC522/556/870", and
  the product code 0x1018:02 encodes the model [EM3E p. 19]. Match the ESI by product code, not
  by name.

## State machine

- **0x000F from Ready to switch on is a setting, on both drives.** Leadshine's 0x5004:0F bit 2
  chooses whether 0x000F enables directly (T3 + T4) or not [EL8 pp. 65–66; EM3E p. 23]. The EL8
  table gives 0x5004:0F a default of 0, so direct enable is presumably off; the EM3E manual
  gives no default. Both manuals' enable sequences go 0x0006, 0x0007, 0x000F, checking the
  statusword in between [EL8 p. 185; EM3E p. 34].
- **Statusword values after enable carry vendor bits.** EL8: 0x0237 in Operation enabled,
  0x0250 in Switch on disabled (bit 9 remote and bit 4 voltage set) [EL8 p. 178]. EM3E's own
  table shows 0x8237 / 0x1237 / 0x1637 depending on mode [EM3E p. 36]. Mask before comparing.
- **EL8 statusword extras**: bit 8 "abnormal stop" (limit, halt or quick stop) in PP, HM and
  CSP; bit 14 "a motion parameter is 0" in PP and HM; bit 15 "origin found" [EL8 pp. 122, 185,
  191, 193]. Bit 15 as a homed flag in HM, CSP and PP is enabled by Leadshine's 0x5012:04 bit 12
  [EL8 p. 66]. In PP, bit 15 is the inverse of bit 12 [EL8 p. 191].
- **EM3E bit 9 (remote) is 0 below Pre-Op, and then the controlword is ignored** [EM3E p. 36].
- **Fault reset**: rising edge on bit 7; while bit 7 stays 1, all other commands are ignored
  [EL8 p. 122]. On the EM3E, 0x0080 clears every alarm except over-voltage and over-current,
  which need a power cycle [EM3E p. 32]. An out-of-range electronic gear on the EL8 leaves the
  state machine in Fault after the panel alarm clears; it still needs 0x0080 [EL8 p. 181].

## Option codes

| Object | EL8-EC | EM3E | Differs from the profile |
|---|---|---|---|
| 0x605A quick stop | 0–3, 5–7; default 2 | 0–7; **default 6** | 3 and 7 ramp on 0x60C6 (max deceleration), not current limit; EM3E 0 and 4 stop at once (4 stays in Quick stop active); no 8 |
| 0x605B shutdown | 0, 1; default 0 | not listed | EL8 **0 = stop by P05.06**, which defaults to a braking stop, not a coast |
| 0x605C disable operation | 0, 1; default 0 | not listed | as 0x605B |
| 0x605D halt | 1–3; default 1 | 1–4; default 1 | 3 = 0x60C6; EM3E 4 = stop at once |
| 0x605E fault reaction | 0–2; default 0 | not listed | EL8 0 = stop by alarm type (P05.10 / P05.16) |

[EL8 pp. 68, 122–124, 181; EM3E pp. 27, 48]. On the EL8, in CST and PT the ramps use 0x6087
instead, and in HM 0x609A replaces 0x6084 [EL8 pp. 123–124]. **P05.06 (0x2506)** sets how the
EL8 stops when disabled: servo braking, coast or dynamic brake, ending in dynamic brake or free
run; default 0 is servo braking into dynamic brake, and it takes effect after a restart [EL8 p.
101]. Drive-side alarms always stop by alarm type, whatever 0x605E says [EL8 p. 124].

**EL8 halt is inconsistent in the manual**: the controlword table marks bit 8 as unused in
CSP, CSV and CST [EL8 p. 184], while 0x605D lists CSP and CSV [EL8 p. 124]. 0x605D also sets the
deceleration used on a mode change [EL8 p. 124].

**EM3E quick stop may trip a fault by default.** Leadshine's 0x22B4 = 0 (default) makes a quick
stop raise alarm 570 (0x5441); only 0x22B4 = 1 uses 0x605A [EM3E pp. 22, 30]. The manual does
not say whether this covers controlword bit 2 or only a quick-stop input (EMG, 0x60FD bit 23)
[EM3E p. 25]. Test it before relying on T16. **EM3E 0x2007** sets whether the shaft is held
(1) or free (0, default) while disabled [EM3E p. 21]. Brake close and release delays are
Leadshine's 0x4003:01/02 (250 ms each by default); the manual does not say whether the state
machine waits for them [EM3E p. 22].

## Limit switches

- **EL8 P05.04 (0x2504)**: 0 (default) blocks motion towards an active limit; 1 ignores
  POT/NOT; 2 makes either limit raise **Er260, a fault** [EL8 p. 101]. Er260 maps to 0x603F =
  0x7329 [EL8 p. 316].
- **EM3E 0x22A9**: 0 (default) stops normally, 1 ignores, 2 raises alarm 260 [EM3E p. 22].
- **Software limits 0x607D**: EL8 accepts them only in Pre-Op, uses them only in absolute moves
  in CSP and PP, and with an incremental encoder only after homing [EL8 p. 183]. Whether 0x607C
  is added to them is set by 0x5012:04 bits 2–3 [EL8 pp. 182–183]. On the EM3E they are off by
  default and need save + power cycle after a change [EM3E p. 27].

## Homing

- **EL8-EC: all methods −6 to 37 except 36** [EL8 pp. 130, 192]. 35 and 37 both set the current
  position and **work without Operation enabled** [EL8 p. 216] (0x5012:04 bit 10 is related
  [EL8 p. 66]). 0x6098 defaults to 19 [EL8 p. 130]. Its data type is given as UINT8 on one page
  and I8 on another [EL8 pp. 130, 192]; the negative methods need it signed.
- **EL8 negative methods are torque end stops** (threshold P05.39, settle time P05.37,
  Leadshine's):

  | Method | Search | Then |
  |---|---|---|
  | −1 / −2 | positive / negative, high speed | reverse at torque, home on first index after torque drops |
  | −3 / −4 | positive / negative, high speed | reverse at torque, home where torque drops (no index) |
  | −5 / −6 | positive / negative, low speed | home at the torque threshold, no reversal |

  [EL8 pp. 130, 194–196]. Leadshine's 0x5012:04 bit 7 can make 33/34 use the torque limit
  instead of the index [EL8 p. 66].
- **EL8 homing errors**: hitting the opposite limit sets statusword bit 13 and stops at once
  [EL8 pp. 196–197, 215]; homing errors also raise alarm Er890 unless 0x5012:04 bit 9 = 1 [EL8
  pp. 66, 313].
- **EM3E: methods 17–30, 35 and 37 only**, so none that use an index pulse. 37 is
  recommended [EM3E pp. 39, 42]. 0x6098 range is 1–100, unsigned: **no negative methods**
  [EM3E p. 28]. 0x5012:04 bit 0 makes a limit stop homing as an error; bits 2–3 decide whether
  0x6064 ends at 0x607C or at 0 [EM3E p. 23].
- **EM3E with a master that homes itself**: the FAQ describes masters that home in CSP
  (0x6060 = 8) or switch 8 then 6; 0x6060 must then be in the PDO [EM3E p. 53].

## Units and scaling

- **EL8 positions are in "command units", velocities in command units/s**, set by an electronic
  gear [EL8 pp. 125–129]. 0x6080 is in rpm [EL8 p. 128]. Torque objects are in 0.1 %
  [EL8 p. 127].
- **The EL8 gear rule is Leadshine's**: if 0x6092:01 differs from the encoder resolution
  0x608F, the gear is resolution / 0x6092:01 (0x6092:01 is "pulses per revolution"); if equal,
  0x6091 applies [EL8 pp. 129, 182]. The manual writes the second case as 0x6091:01 / 0x6092:01,
  which looks like a typo for 0x6091:01 / 0x6091:02. **P00.08 (0x2008), when not 0, overrides
  0x6092** [EL8 pp. 73, 182].
- **EL8 gear limits**: ratio 0.001–8000 with the 23-bit encoder (≥ 1049 command units per
  rev), 0.001–125 with the 17-bit encoder (≥ 17); outside it, ErA00 or Er1B1 [EL8 pp. 181–182,
  312]. 0x6092 is "only valid" in Pre-Op while 0x6091 takes effect at once [EL8 p. 182].
- **P05.20 (0x2520) picks the position unit** for PP, HM and CSP: encoder, command, or
  10000 pulses/rev — **default 2, 10000 pulses/rev**. It takes effect after restart and clears
  the position [EL8 p. 103]. Its interaction with 0x6091/0x6092 is not explained.
- **Direction**: 0x607E uses bit 7 for position modes, bit 6 for velocity, bit 5 for torque
  (224 = all), but P00.06 (0x2006) overrides it [EL8 pp. 73, 128].
- **EM3E positions are in pulses, velocities in pulses/s**; there is no factor group. The
  scale is the microstep setting 0x2001 (200–51200, default 10000 pulses/rev) [EM3E pp. 21,
  27]. 0x6080 is in rpm [EM3E p. 28]. 0x607E works only after 0x225C bit 1 = 1; otherwise 0x2051
  sets the direction [EM3E pp. 21, 27].

## Synchronisation

- **EL8**: SYNC0 cycle 250 µs to 10 ms by default (0x5400:01/02), extendable to 125 µs and
  20 ms; a multiple of 250 µs [EL8 pp. 66, 185]. Free run is for PP and HM only [EL8 p. 303].
  Watchdog limits 0x5004:07 / :09 / :0B (default 4) raise Er73B (SYNC0 lost), Er73C (DC error)
  and Er73A (SM2 lost); 0 switches each off [EL8 pp. 65, 316]. 0x5006 masks the sync alarms
  [EL8 p. 66].
- **EM3E**: CSP only in DC mode, cycles **250, 500, 750, 1000, 2000, 4000 or 8000 µs only**
  [EM3E p. 33]. Other periods (the FAQ names 0.9 and 1.1 ms) fail with 0x8736, invalid DC
  period [EM3E pp. 30, 52].

## PDO mapping

- **EL8**: four RxPDO maps 0x1600–0x1603 and two TxPDO maps 0x1A00–0x1A01; up to two Rx and two
  Tx assigned at once, each with up to 8 objects and 32 bytes [EL8 pp. 306, 308]. Remap in Pre-Op;
  it takes effect at SafeOp [EL8 p. 308]. Leadshine's 0x5004:0F bit 0 can block SDO writes to
  the mapping outside OP, bit 1 limits the count to 8 [EL8 pp. 65–66].
- **EL8 default**: 0x1600 = controlword, 0x607A, 0x60B8 (CSP plus touch probe); 0x1A00 =
  0x603F, statusword, 0x6061, 0x6064, 0x60B9, 0x60BA, 0x60FD. 0x1601–0x1603 hold CSV, CST and
  homing sets; 0x1A01 is empty [EL8 p. 307]. The CST set maps 0x6087 though its label says
  0x6084 [EL8 p. 307].
- **EM3E**: the same 0x1600–0x1603 / 0x1A00–0x1A01 layout, up to 8 objects each; default
  assignment 0x1C12 = 0x1600, 0x1C13 = 0x1A00. The manual gives only the object counts (3, 6, 5,
  7 and 7, 0), not their contents [EM3E pp. 19–20]. 0x6061 should be mapped: some masters
  alarm without it [EM3E p. 52].

## Touch probe

- **EL8**: two probes. 0x60B8 bit 2 / bit 10 choose the probe input or the encoder index [EL8
  pp. 132, 284]. The probe inputs share DI5/DI6 and work as probes only while those inputs have
  no other function [EL8 p. 284]. Polarity is in P00.07 (0x2007), after restart [EL8 p. 283].
  Single mode re-arms by toggling bit 0 / bit 8; changing the setup resets the counters 0x60D5–
  0x60D8 [EL8 pp. 283, 286].
- **EM3E**: two probes, on DI1/DI2 by default [EM3E p. 15]. 0x60B9 bits 6 and 7 show the
  actual level of probe 1 and 2, which the profile leaves reserved [EM3E p. 37]. Enable bits
  act on a rising edge [EM3E p. 37].
