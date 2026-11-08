# Mitsubishi Electric MR-J4-TM (EtherCAT)

**Read 2026-11-08**: Mitsubishi Electric, *MR-J4-_TM_ Servo Amplifier Instruction Manual
(EtherCAT)*, SH(NA)030208ENG, revision E (November 2018). Mitsubishi Electric publishes its
manuals at https://www.mitsubishielectric.com/fa/ (download section). Page numbers in brackets
are PDF pages, not the printed chapter-page labels.

The MR-J4-_TM_ is a multi-network servo amplifier. It speaks EtherCAT only with the HMS
**ABCC-M40-ECT** network module plugged in, a variant made for MELSERVO [pp. 14, 26]. Behaviour
differs by the amplifier's own **software version** (A0, B0 to B4 are named); the manual flags
each difference, and the main ones are noted below. Parameters (`Pr. PA01` …) are described in
the separate *MR-J4-_TM_ Servo Amplifier Instruction Manual*, which was not read. The manual
contradicts itself in a few places; those are marked.

## Identity and the network module

- **0x1009, 0x100A and 0x1018:04 describe the network module**, not the amplifier. The
  amplifier's own name, hardware and software versions and serial number are in Mitsubishi's
  0x2D30–0x2D33 [pp. 147, 149]. From software B3, 0x1008 returns only "MR-J4-TM"; the full model
  is in 0x2D30 [p. 146].
- **Use the ESI, not the online object list**, with the older AB6916-B module: Get OD List reads
  only the first 710 objects [p. 26]. **SDO Complete Access is not supported** [p. 36].
- **Leaving EtherCAT OP re-initialises the amplifier's internal state** [p. 22]. Shut down
  with the controlword (Shutdown) and go to Pre-Op before cutting the network, or it raises
  AL. 86.1 [p. 24].

## State machine

- **Skipped transitions are accepted.** 0x000F works from Switch on disabled or Ready to switch
  on and goes straight to Operation enabled; Switch on (0x0007) from Switch on disabled goes
  straight to Switched on [p. 40].
- **No T16.** Quick stop active always ends in Switch on disabled, because only quick-stop
  option 2 exists (below) [pp. 39–40, 119].
- **The statusword is not sent in Not ready to switch on** [p. 45]. Bit 4 means the DC bus is
  above the ready (RA) level [p. 44]. Bit 11 (internal limit) also covers the hardware stroke
  ends LSP/LSN [p. 44].
- **Fault reset over an unreliable link: hold bit 7 for at least 10 ms** [p. 40].
- **Manufacturer control and status words** sit beside the profile ones: Control DI 1–3
  (0x2D01–0x2D03: gain switching, proportional control, warning reset) and Status DO 1–3, 5, 7
  (0x2D11–0x2D17: in-position, torque limiting, zero speed, homed, STO active …), all
  Mitsubishi's [pp. 41–48]. They are in the default PDOs.

## Option codes

| Object | MR-J4-TM allows | Default | Differs from the profile |
|---|---|---|---|
| 0x605A quick stop | **2 only** | 2 | 1, 3–8 refused; in cst and tq, quick stop drops straight to Switch on disabled and stops on the **dynamic brake** |
| 0x605B shutdown | absent | — | not in the dictionary |
| 0x605C disable operation | absent | — | not in the dictionary |
| 0x605D halt | **1 only** | 1 | halt works in pp, pv, tq, hm, pt and jg; **ignored in csp, csv and cst** |
| 0x605E fault reaction | absent | — | not in the dictionary |

[pp. 119–120, 143, 190–191]. With 605A = 2, csp, csv, pp, pv, hm, pt, jg and idx ramp down on
0x6085 [p. 119]. In tq, halt ramps the torque demand to 0 on 0x6087 whatever 605D says
[p. 120]. 0x605A and 0x605D are stored in Pr. PT68 [pp. 190–191].

## Modes of operation

- **Modes 1, 3, 4, 6, 8, 9, 10, plus Mitsubishi's −100 (jog), −101 (point table) and −103
  (indexer)**, the last three from software B2 [pp. 15, 191]. No vl and no ip [p. 193].
- **Pr. PA01 limits which modes 0x6060 accepts** and sets the start-up mode: cyclic → 8 (csp),
  profile → 1 (pp), point table → −101, indexer → −103 [pp. 49, 192]. The extracted table
  does not show which modes each setting allows; check the PDF. 0x6502 shows all modes
  whatever PA01 says [p. 193].
- **A mode change into or out of a position mode happens only at zero speed** (Status DO 2 bit 3);
  otherwise 0x6061 keeps the old mode. Changes to the mode-specific controlword bits are ignored
  until the switch completes, so keep sending both modes' setpoints until 0x6061 changes
  [p. 49].
- **DC is required in csp, csv and cst up to software B3**; free run there needs B4 and a written
  0x1C32:02 cycle time [pp. 15–16, 20]. SYNC0 jitter must stay under 2 µs [p. 16].
- **Cycle time is 0.25, 0.5, 1 or 2 ms, set in 0x1C32:02 in Pre-Op** [pp. 30, 157]. The shift
  times 0x1C32:03 / 0x1C33:03 are computed by the drive; writing them is refused [p. 30].
- **0x60B2 torque offset (from B2) acts only in csp, csv and cst**, and is added to Pr. PE47 if
  both are set. It can jerk the motor at servo-on or on a change to homing [p. 126].

## Units and scaling

- **Velocities are fixed at 0.01 r/min** (0.01 mm/s on linear motors), torques at 0.1 % of
  rated [pp. 50–51, 197–199]. 0x6080 is in whole r/min [p. 203].
- **0x6083, 0x6084, 0x6085 and 0x609A are times in ms**, not accelerations: the time to go
  from 0 to rated speed, or from rated speed to 0 [pp. 204, 206]. The slope therefore depends
  on the motor's rated speed. 0x6085 = 0 means 100 ms [p. 204].
- **0x6086 is always −1 (S-curve)**; no other value can be written [p. 205]. Section 5 gives the
  default as 0 [pp. 58, 61], the dictionary as −1.
- **0x6091 is the electronic gear** (Pr. PA06 / PA07). Up to software B2, any value other than
  1:1 in a cyclic mode raises AL. 37 [pp. 51, 212].
- **0x608F, 0x6092, 0x60A8 and 0x60A9 are read-only**, derived from the encoder and from Pr. PT01
  (unit: mm, inch, degree, pulse) and PT03 (×1 to ×1000); writes are refused [pp. 211–214].
  **The cyclic modes work in pulses only**; mm, inch and degree apply to the profile and point
  table modes [pp. 50, 212–213].
- **In pp, 0x607A is limited to ±999 999** (−360 000 to 360 000 in degrees); csp takes the full
  32 bits [p. 201]. With the default 1:1 gear and a 4 194 304 pulse/rev encoder [p. 17], one pp
  move is less than a quarter of a turn.
- **The degree unit makes 0x6064 wrap at 0–359.999°** and disables relative moves in pp
  (AL. F4.8) [pp. 59, 124]. Direction is chosen with 0x60F2 bits 6–7 [pp. 124, 196].
- **0x607E accepts only 00h or C0h** (position and velocity reversed together; E0h, with torque
  too, is also listed from B0 — the page contradicts itself) [p. 211]. It writes Pr. PA14 and
  PC29 and takes effect only after the parameter-enable step (below) [p. 122].
- **0x6077 is INTEGER16** in the dictionary and the default PDO sizes; section 5 lists it as
  INTEGER32 [pp. 51, 199].

## Parameters over SDO

- **Pr. groups PA–PN are objects 0x2001–0x25A0** (Mitsubishi's), one INTEGER32 each [p. 132].
- **SDO writes are lost at power-off** unless saved with 0x1010:01 = "save". The save writes
  everything and **takes up to about 25 s**; wait for bit 0 before switching off [pp. 140, 148].
  Only sub-index 1 (save all) exists [p. 148].
- **Parameters marked `*` take effect only after an enable step**: leaving OP, or writing 1EA5h
  to Mitsubishi's 0x2D34 in Pre-Op (up to about 100 ms; poll for 1). Parameters marked `**`
  need a save and a power cycle [pp. 132–133].
- **0x1011 restore defaults also erases the home position** after the power cycle [p. 149].

## Homing

- **Standard methods 3–8, 11, 12, 19–24, 27, 28, 33, 34, 35 and 37** (0x60E3) [p. 208]. Not 1,
  2, 9, 10, 13, 14, 17, 18, 25, 26, 29, 30.
- **Both 35 and 37, and both work with the servo off.** Mitsubishi's −3 (data set) does the same
  but needs the servo on [pp. 71, 88].
- **Negative methods**: −1 dog, rear end, then Z; −2 count type (fixed distance after the dog
  front, then Z); −3 data set; −4 stopper (hard stop, torque-limited by 0x60E0, held for
  Pr. PT10); −6 to −11 further dog and dogless variants. All of these start in the forward
  direction; adding −32 gives the reverse (−33, −34, −36, −38 to −43) [pp. 70, 84–95, 208].
- **On a stroke end**, methods 3–6, 19–22, 33, 34, the stopper type and dogless −11/−43 stop with
  AL. 90. Methods 7, 8, 11, 12, 23, 24, 27, 28 and the other dog types reverse there. The software
  limit cannot stand in for a stroke end [pp. 70–71, 77–95].
- **0x607C cannot be written.** It shows the home position the drive found or restored from
  EEPROM (0 without an absolute encoder); the offset comes from Mitsubishi parameters [pp. 67,
  205]. Section 5 lists it as read-only, the dictionary as rw-but-refused.
- **0x6098 default**: −1 in section 5, 37 in the dictionary [pp. 67, 205]. Write it explicitly.
- **Bit 12 stays set after a successful homing**, so on re-entering hm the status already reads
  "completed". It clears at power-on (incremental), on start, or when the home position is
  erased [p. 68].
- **The statusword can lag bit 4 by up to 50 ms**; after bits 12 and 10 are set, wait 8 ms more
  before trusting the position [p. 68].
- **Before leaving hm, the manual says to write 0 to 0x607A** [p. 69] — not "target = actual".
  This is only safe if the home position is 0; otherwise follow the actual position.
- In homing, a stroke end stops the motor on the deceleration time constant; keep the speeds
  low [p. 67]. Linear, fully closed and DD setups must pass the Z-phase once first (AL. 90.5)
  [p. 69]. The indexer method allows only −1, −33, −3, 35, 37 [pp. 69, 210].

## Monitoring and limits

- **0x6065 defaults to 0x00C00000 pos units**; FFFFFFFFh turns bit 13 off [p. 194]. **0x6067
  above FFFEh is refused**; FFFFFFFFh forces target reached on [p. 195].
- **0x60E0 / 0x60E1 = 0 means no torque at all**, and 0x2D20 (Mitsubishi's speed limit for
  torque modes) = 0 means no speed. Both are in the default RxPDO, so the master must send
  real values from the first cycle [p. 31]. 0x2D20's default is 50 000 on p. 56 and 5 000 on
  p. 65.
- **Software limit (0x607D) clamps the target** and raises AL. 98; it works only while homed, in
  csp, pp, pt and jg. Min ≥ max disables it [pp. 121, 202].
- **AL. 69 (command error) erases the home position.** It is raised when a csp target runs more
  than 2³⁰ past a stroke end or the software limit [pp. 121, 130].
- **0x603F and 0x1003 carry FF + alarm number** (e.g. FF20h for AL. 20) from software B2; up to
  B1 they show only 1000h [pp. 146, 190].
- **AL. 86.1 (sync loss)**: threshold in 0x10F1:02 / Pr. PN02, 7 ms by default; 0 disables it and
  then the motor is not stopped on a communication loss [p. 150]. Mapping Mitsubishi's
  0x2D23/0x2D24 counters adds a PDO watchdog (AL. 86.2) [p. 130].

## PDO mapping

- **One RxPDO and one TxPDO** per cycle, chosen from 0x1600–0x1603 / 0x1A00–0x1A03; each up to
  32 objects and 64 bytes. Remap only in Pre-Op [pp. 20, 33].
- **Defaults are mode-agnostic**: 0x1600/0x1A00 (assigned) carry csp, csv, cst and hm setpoints
  with torque limits, touch probe and Mitsubishi's Control DI / Status DO (29 / 41 bytes);
  0x1601 adds the profile objects (45 bytes); 0x1602/0x1A01 serve pt, jg and idx [pp. 31–32].
- An SDO write to an object mapped in the RxPDO is refused [p. 37].

## Touch probe

Two probes on inputs TPR1 and TPR2, latched to 55 µs. TPR2's rising edge can be latched to 2 µs
(Pr. PD37), which turns off the encoder pulse output [pp. 115, 119]. The encoder zero as a
trigger needs software B2 [p. 116]. Probe pulses must be at least 0.5 ms high and low [p. 118].
Not available in the indexer method [p. 115].
