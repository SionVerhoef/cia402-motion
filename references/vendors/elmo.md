# Elmo Gold Line drives

**Read 2026-11-08**: Elmo Motion Control, *Gold Line Drive Administration Manual*, MAN-G-ADMING,
Ver. 1.100 (December 2012). Elmo publishes its manuals at https://www.elmomc.com. Page numbers
are given in brackets.

**This is an old, unfinished document, and not Elmo's CiA 402 manual.** It dates from 2012, and
several chapters are only headings with a note that they are still to be written: enabling the
motor and the CANopen state machine, the profilers and stop manager, fault handling, and the
communication overview [pp. 8, 10, 14–16]. It points to the *Elmo Gold CANopen Manual* for the
objects [pp. 24, 31, 94]. So this page has **nothing on quick stop, the option codes or the
state transitions**, and little on PDO mapping. What it does cover in depth is homing, touch
probe and the link between Elmo's own commands and the profile objects. Current Gold firmware
may differ on every point here.

The page covers the Gold drive family in general. The manual names no individual models,
except old hardware with the SCORE module (e.g. G-GUI) for one input limitation [p. 46].

## Two command sets on one drive

- **Gold drives take Elmo's two-letter commands (`UM`, `IL[]`, `GI[]`, `HM[]` …) as well as
  CiA 402 objects**, and most commands have an equivalent object [pp. 83, 94]. Motion follows
  DS 402 v3.0 over both CAN and EtherCAT [p. 83].
- **Mixing them conflicts, and the last write wins.** Each parameter has a single live copy that
  the profilers and loops use, so a value set through an Elmo command and one set through an
  object overwrite each other [pp. 83–84]. A commissioning tool session (Elmo Application
  Studio) left in a different state from what the master assumes is a source of surprises.
- **Some homing and capture set-up exists only as Elmo commands**, with no object named in the
  manual: input function and polarity (`IL[]`) and routing an input to an encoder's index or
  strobe channel (`GI[]`). They are stored in the drive and must be set once, before DS 402
  homing or touch probe can work [pp. 25, 40].

## Unit mode gates the operating modes

- **Elmo's unit mode `UM` decides which 0x6060 modes are allowed.** UM 1 (current) allows only
  profile torque; UM 2 (velocity) adds profile velocity, with homing "for future use"; UM 5
  (position) allows profile torque, velocity, position, interpolated position and homing
  [pp. 91–92]. UM 3 is an open-loop stepper mode used mainly by the set-up wizards [p. 92].
- **0x6060 can change at any time, also with the motor on; `UM` only with the motor off**
  [pp. 91–92]. So homing needs UM 5; in UM 2 it is listed as not yet available.
- **The manual lists no cyclic synchronous modes (8, 9, 10).** Only the profile modes,
  interpolated position and homing appear [p. 92]. That is what this 2012 document lists, not
  necessarily what current firmware supports.
- Synchronisation of the profile task follows SYNC on CANopen and distributed clocks on
  EtherCAT [p. 85].

## Homing

- **Supported standard methods: 1–14, 17–30, 33, 34 and 35** [pp. 41–42]. The text speaks of
  36 methods [p. 22], but the table stops at 35; **37 is not listed**.
- **Every switch-based method needs inputs routed first.** Methods with an index pulse need the
  motor index routed to the sensor's index channel; methods with a home switch need the home
  input routed to the sensor's strobe channel and defined as "home" with `IL[]`; limit-switch
  methods need the limit inputs defined. Index and strobe must be on the same sensor [pp. 40–42].
  Methods 17, 18 and 35 need no routing [pp. 41–42].
- **Homing runs on the main position feedback** unless Elmo's object 0x20B0:08 (or `OV[54]`)
  selects another sensor [pp. 24, 40].
- **On completion the home offset becomes the position, and the software position limits move
  with it** [p. 22].
- **DS 402 homing, touch probe and Elmo's own homing (`HM[]`/`HF[]`) exclude each other.**
  Selecting homing in 0x6060 while one of the others holds the capture hardware is refused with
  an Elmo error code [pp. 43, 46–47]. Homing on the strobe input also cannot share a sensor with
  output compare; index homing can [pp. 43, 46].
- **Negative methods −1 (reverse) and −2 (forward) home on a block**, PLCopen style: the drive
  stops when the torque limit is reached and the speed has fallen below 5 % of the commanded
  speed [pp. 22, 43–44]. The limits are in Elmo's object 0x2020: sub 1 torque in ‰ of rated
  torque, sub 2 time limit in ms, sub 3 distance limit in counts; 0 disables each, and the time
  or distance limit raises an error if no block is found in time [pp. 44–45].
- **Homing on a block does not set the position.** It only stops; 0x607C is not used. Set the
  position afterwards with an index or current-position method [pp. 22, 44].
- **The drive stays in homing mode after −1/−2 finish**, success or error; the master must
  write a new 0x6060 [p. 45]. Bit 12 is done and bit 13 is error, as in the profile [p. 44].
- 0x609A is used for both acceleration and deceleration [p. 22].

## Touch probe

- **Touch probe 1 is the sensor's index input, touch probe 2 its strobe input** [p. 31]. Any
  digital input can be routed to either with `GI[]` [pp. 31, 38]; inputs not routed this way
  cannot be used for touch probe [p. 21]. The sensor is the main feedback unless Elmo's object
  0x20B0:07 selects another [p. 31].
- **On EtherCAT, touch probe 2's positions cannot go in a TxPDO.** Read 0x60BC/0x60BD by SDO
  [p. 31].
- **The first event is always a rising edge.** A falling edge that comes before the first
  rising edge is ignored, so a probe armed for the falling edge while the input is already high
  misses that edge [pp. 22, 31, 46].
- Only the last capture is kept [p. 31]. Captures are hardware-timed (under 5 µs), but
  consecutive events need 250 µs between them [p. 31].
- **Elmo's object 0x2E10 homes on the last capture**: writing 0 or 1 sets the position from the
  rising or falling capture plus 0x607C. SDO only; the SDO reply means done [pp. 32, 36–37].

## Units and position

- **Position and velocity are in user units through the profile's factor objects.** With
  0x606A = 0 the velocity comes from the position sensor; with 0x606A = 1 from a separate sensor,
  and the gear ratio then sets how the two encoders relate. Only the product of gear ratio and
  feed constant matters [pp. 92–93].
- **The user position wraps between the limits in 0x607B**; Elmo's `XM[1]`/`XM[2]` override
  them [p. 85].
- **Enabling the motor sets the demand position to the actual position** [p. 85].
- **Torque and current objects are in ‰ of rated torque**, as in the profile [p. 45].
- A count on an A quad B encoder is a quarter of a line [p. 95].

## Faults

- **Elmo's `MF` command latches the motor-fault reason as a bit field** [pp. 86–87]. The EMCY
  codes include several in the manufacturer range: 0xFF10 cannot start motor (check parameters),
  0xFF20 safety input not active, 0xFF30 and 0xFF34 numeric overflow [p. 88].
- **0x1002 mirrors Elmo's status register `SR`, not latched**: amplifier status, motor enabled,
  fault, unit mode, recorder state [pp. 88–89].
- **Input 1 is dedicated to safety and cannot be reassigned** [p. 90]. An input set as "abort"
  disables the motor and it stays off when the input returns; an "inhibit" input disables it
  only while active [p. 90].
