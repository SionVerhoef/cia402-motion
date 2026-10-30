# Templates

`FB_Cia402Axis` is a PLC function block for one CiA 402 drive. It brings the drive through its
state machine into Operation enabled in the mode you ask for, homes it, switches modes, takes
it down again, with a quick stop if you ask for one, and resets faults, keeping to the rules in
`../references/state-machine.md`.

> **Status: reviewed, not run on a drive.** twincat-st's `st_review.py` reports no high
> findings and one medium (CP23: 11 pins, where PLCopen suggests about 10), and
> `tests/test_templates.py` runs the FB's own text against a simulated drive. It has never
> been compiled in TwinCAT or CODESYS, and it has never driven a real drive. Test it with
> reduced torque and speed limits before anyone stands near the machine. It is not a safety
> function: STO, SS1 and safe stops belong in a safety controller
> (`../references/safety-boundary.md`).

## When to use it

The FB does for one axis what a motion runtime's drive layer does: the state machine (as
`MC_Power` does), fault reset (`MC_Reset`), the mode of operation and drive-based homing. It
generates no trajectory: `MC_MoveAbsolute` and the other motion blocks have no counterpart here.

- **Use it when the drive makes the motion**: profile position, velocity or torque (PP, PV, PT)
  and drive-based homing. A stepper doing point-to-point moves, a conveyor or spindle in velocity
  mode, an axis that only homes. Also on a PLC with no motion runtime.
- **Where TwinCAT NC or CODESYS SoftMotion can drive the axis, use that instead.** Link the
  drive to an NC or SoftMotion axis and move it with the MC_ blocks (the **twincat-motion** skill
  covers TwinCAT). That gives you the trajectory, gearing, cams and coordinated motion. In CSP
  this FB leaves the trajectory to you, which is only worth it without a motion runtime.
- **Never both on one drive.** An NC or SoftMotion axis and this FB would both write 0x6040.

## Files

| File | What |
|---|---|
| `FB_Cia402Axis.TcPOU` | The function block, TwinCAT 3 format (UTF-8 with BOM, CRLF) |
| `E_Cia402State.TcDUT` | The drive's state, decoded from the statusword |
| `E_Cia402Step.TcDUT` | The FB's own steps |
| `ST_Cia402Drive.TcDUT` | One axis' process data: what goes to and comes from the drive |
| `ST_Cia402Config.TcDUT` | Timeouts, reset retries, quick-stop handling |
| `FB_Cia402Axis.st` | All five as one plain Structured Text file, the same text |

The TwinCAT files were made with twincat-st's `tcpou.py` and pass its `check`. To add them to a
project under other names, use `tcpou.py new` and `set` for each part, so each object gets a
fresh GUID. The `.st` uses the CODESYS-family syntax TwinCAT shares (`{attribute
'qualified_only'}`, a typed enum `) INT;`); another IEC 61131-3 environment may need those two
changed.

## Interface

| Pin | Type | |
|---|---|---|
| `bEnable` | BOOL in | TRUE: Operation enabled in `nMode`. FALSE: stop with T5 (0x605C decides how), then T10 |
| `nMode` | SINT in | The 0x6060 code. 6 means home: `bValid` then says homed. Change it at standstill |
| `bReset` | BOOL in | Rising edge: clear the error; from Fault, run the reset first |
| `bQuickStop` | BOOL in | TRUE, one scan is enough: quick stop, 0x0002 held, over `bEnable`. See *Quick stop*. Not a safety function |
| `stConfig` | `ST_Cia402Config` in | The defaults are in the type. Not checked: a zero timeout times out at once |
| `bValid` | BOOL out | Enabled in `nMode`: the set-points in `stDrive` are yours |
| `bBusy` | BOOL out | On the way to what `bEnable` asks |
| `bError`, `nErrorID` | out | The error codes are below |
| `eDriveState` | `E_Cia402State` out | For an HMI or a diagnosis |
| `stDrive` | `ST_Cia402Drive` in-out | Fill its inputs before the call, send its outputs after |

**Set-points.** From `bValid` on, 0x607A, 0x60FF, 0x6071 and `stDrive.nModeBits` (the PP
handshake, halt) are yours. Start a trajectory from where the FB left them: on every rising
edge of `bValid`, which comes after enabling, after homing and after a mode switch. Before T4,
and whenever the drive is out of Operation enabled, the FB holds them where enabling cannot
move the motor: 0x607A at 0x6064, 0x60FF and 0x6071 at 0, `nModeBits` at 0. While the drive is
still enabled and they are not yours (on the way down, in an error, during a mode switch), the
FB leaves them as you left them, so it never steps a set-point the drive is following. A mode
switch makes the new mode's own set-point safe a scan before it writes 0x6060.

**Errors.** An error takes the drive down the way `bEnable` FALSE does, and the FB stays down
until `bReset`. With `bEnable` still TRUE it then enables again, as PLCopen `MC_Power` does after
`MC_Reset`. `nErrorID` keeps the first error; `eDriveState` shows Fault if the drive faulted
since. In Error the FB keeps taking the drive down without a timeout of its own, and `bBusy` is
FALSE: watch `eDriveState`.

| `nErrorID` | Meaning |
|---|---|
| 16#8101–16#8104 | The drive did not take T1, T2, T3 or T4 in `tStateTimeout` |
| 16#8105 | 0x6061 never showed `nMode`: the drive may not have the mode (0x6502) |
| 16#8106 | A step of the way down did not end in `tStopTimeout` |
| 16#8107 | Homing did not end in `tHomingTimeout` |
| 16#8108 | `bQuickStop`: the drive did not take 0x0002 in `tStateTimeout`. The FB goes on with T5 |
| 16#8110 | The drive is in Fault: read 0x603F |
| 16#8111 | Still in Fault after `nResetAttempts` resets: the cause is still there |
| 16#8112 | Quick stop active, not asked for with `bQuickStop` |
| 16#8113 | The drive moved where the FB did not ask: out of the state it was holding, during a mode switch, or out of a reset |
| 16#8114 | Homing error, statusword bit 13 |
| 16#8115 | The statusword matches no state and its fault bit is 0, or reads Not ready after the drive had left it (inputs that are not the drive's) |
| 16#8120 | `nMode` is 0 |

## Quick stop

**Asking for one.** `bQuickStop` TRUE sends 0x0002 on the same scan and holds it, over
`bEnable`, from any step; one scan of it is enough. Only a fault reset that has begun runs to
its end first. In Operation enabled the word is T11, and 0x605A decides how the motor stops: the
FB does not write it, and what a drive offers differs by vendor
(`../references/state-machine.md`). From Ready to switch on or Switched on the drive goes
straight to Switch on disabled, and a T4 still on its way meets T11, never T9. `bValid` falls at
once. It is not an error: `bError` stays FALSE. In Error the word replaces T5, and the last word
kept for a statusword that decodes to nothing.

**A drive that does not take it.** If the drive has reached neither Quick stop active nor Switch
on disabled after `tStateTimeout`, that is 16#8108, and the FB takes it down with T5, so that
asking for a stop never leaves an axis harder to stop. Beckhoff's EL72x1 in DS402 has no quick
stop and reserves controlword bit 2 there, and LinMot's C125x-MI has no 0x605A
(`../references/vendors/`). What 0x0002 does on such a drive is not in those pages: try it before
relying on it.

**Held down.** `bQuickStop` falling does not end the stop, and the FB never sends T16. The drive
ends in Switch on disabled and stays there, through an error or a fault reset too, until a scan
finds it there with `bQuickStop` and `bEnable` both FALSE; a new `bEnable` then enables it.
`bReset` does not release it. While it holds with `bEnable` TRUE, `bValid`, `bBusy` and `bError`
are all FALSE, which is how to tell it from a drive on its way. For a line stop, `bEnable :=
bRun` and `bQuickStop := NOT bLineOk`: the line coming back restarts nothing, `bRun` has to fall
and rise.

Not a safety function: `../references/safety-boundary.md`. To pause an axis and carry on, use
halt, bit 8 of `nModeBits`. A quick stop ends with the drive switched off.

**How it ends.** The same for a quick stop you asked for and one the drive went into itself,
from its own input or another source (that one is 16#8112). The FB holds 0x0002 and waits for
the stop to end. With 0x605A 0–4 the drive leaves by itself (T12). With 0x605A 5–8 it stays in
Quick stop active at standstill: set `stConfig.bQuickStopStays`, and `nStandstillWindow` to the
position jitter at standstill, and the FB sends T12 once 0x6064 has stayed inside the band for
`tStandstill`. Without the flag the FB waits for ever: safe, but stuck. The flag needs 0x6064
copied in, and a `tStandstill` longer than the drive's position update period.

## Wiring it, in TwinCAT

```
VAR
    fbAxis1       : FB_Cia402Axis;
    stAxis1       : ST_Cia402Drive;
    stConfig1     : ST_Cia402Config;
    fbValidRise1  : R_TRIG;
    bAxis1On      : BOOL;    // from the application
    bAcknowledge  : BOOL;    // from the HMI
    bLineStop     : BOOL;    // from the application; not a safety input
    nTrajectory1  : DINT;    // your CSP set-point generator's output
    nStatus1   AT %I* : UINT;   // link: 0x6041
    nDisplay1  AT %I* : SINT;   // 0x6061
    nActual1   AT %I* : DINT;   // 0x6064
    nControl1  AT %Q* : UINT;   // 0x6040
    nModeOut1  AT %Q* : SINT;   // 0x6060
    nTarget1   AT %Q* : DINT;   // 0x607A
END_VAR

stAxis1.nStatusword     := UINT_TO_WORD(nStatus1);
stAxis1.nModesDisplay   := nDisplay1;
stAxis1.nPositionActual := nActual1;
fbAxis1(bEnable := bAxis1On, nMode := 8, bReset := bAcknowledge, bQuickStop := bLineStop,
        stConfig := stConfig1, stDrive := stAxis1);
fbValidRise1(CLK := fbAxis1.bValid);
IF fbValidRise1.Q THEN
    nTrajectory1 := stAxis1.nTargetPosition;   // start where the FB left it
END_IF
IF fbAxis1.bValid THEN
    // ... your trajectory moves nTrajectory1 on from here ...
    stAxis1.nTargetPosition := nTrajectory1;
END_IF
nControl1 := WORD_TO_UINT(stAxis1.nControlword);
nModeOut1 := stAxis1.nModesOfOperation;
nTarget1  := stAxis1.nTargetPosition;
```

Call it in the task that exchanges the drive's process data, once per cycle. 0x6041, 0x6061 and
0x6064 are needed in every mode; copy the outputs your mapping has. ESI files usually give the
controlword and statusword as UINT; the struct holds them as WORD, because the IEC bit
operators are defined on bit strings, hence the conversions. For homing, write 0x6098 and the
speeds 0x6099 by SDO before asking for mode 6.

## PDO mapping

Two mappings for the FB. Each is checked by `cia402.py pdo` in `tests/test_templates.py`. Whether
a drive lets you map these, and in which PDOs, is a device fact: ask **ethercat-esi**, or see the
vendor page. Beckhoff's EL72x1 in DS402, for one, has fixed PDOs of one object each, carries
0x6060/0x6061 only in the optional 0x1608 and 0x1A0E, and has no homing mode
(`../references/vendors/beckhoff.md`).

### CSP, with drive-based homing

`python3 scripts/cia402.py pdo --mode csp,hm --rx 6040 6060 607A --tx 6041 6061 6064 603F`

| PDO | Object | Name | Type | In `stDrive` |
|---|---|---|---|---|
| RxPDO | 0x6040 | Controlword | UINT | `nControlword` |
| RxPDO | 0x6060 | Modes of operation | SINT | `nModesOfOperation` |
| RxPDO | 0x607A | Target position | DINT | `nTargetPosition` |
| TxPDO | 0x6041 | Statusword | UINT | `nStatusword` |
| TxPDO | 0x6061 | Modes of operation display | SINT | `nModesDisplay` |
| TxPDO | 0x6064 | Position actual value | DINT | `nPositionActual` |
| TxPDO | 0x603F | Error code | UINT | not used by the FB: read it on 16#8110 |

### PP, with drive-based homing

`python3 scripts/cia402.py pdo --mode pp,hm --rx 6040 6060 607A 6081 --tx 6041 6061 6064 603F`

| PDO | Object | Name | Type | In `stDrive` |
|---|---|---|---|---|
| RxPDO | 0x6040 | Controlword | UINT | `nControlword`, with `nModeBits` while `bValid` |
| RxPDO | 0x6060 | Modes of operation | SINT | `nModesOfOperation` |
| RxPDO | 0x607A | Target position | DINT | `nTargetPosition` |
| RxPDO | 0x6081 | Profile velocity | UDINT | not in `stDrive`: yours to write |
| TxPDO | 0x6041 | Statusword | UINT | `nStatusword`, bit 12 for the set-point handshake |
| TxPDO | 0x6061 | Modes of operation display | SINT | `nModesDisplay` |
| TxPDO | 0x6064 | Position actual value | DINT | `nPositionActual` |
| TxPDO | 0x603F | Error code | UINT | not used by the FB: read it on 16#8110 |

In PP each move is the handshake in `../references/modes.md`: write 0x607A, set bit 4 in
`nModeBits`, wait for statusword bit 12, clear bit 4. Without 0x6060 and 0x6061 in the mapping,
write 0x6060 by SDO for every mode switch and copy 0x6061, read by SDO, into
`stDrive.nModesDisplay`; otherwise the FB waits for a mode it cannot see and stops with 16#8105.

## What it cannot see

- **Whether the inputs are the drive's.** If the bus stops (EtherCAT WcState ≠ 0, a CANopen PDO
  not received), the inputs may freeze, and the FB keeps reading the last statusword as true.
  Gate on the bus state in your application, and hand bus faults to **ethercat-diagnostics**.
  Inputs that drop to 0 are caught: Not ready after another state is 16#8115.
- **A state the drive has just entered by itself.** Until the statusword shows it, the FB keeps
  sending the word for the state it last saw: bit 7 for a cycle or two after a fault reset
  succeeded, 0x000F for a cycle or two after the drive went into Quick stop active on its own.
- **What a particular drive does.** The vendor list in the FB's header comment is what to check
  on yours.

## How it was tested

`tests/st_subset.py` runs the Structured Text subset these files are written in, and refuses
anything else. `tests/test_templates.py` runs `FB_Cia402Axis.st` with it, against a simulated
drive built on the model drive in `tests/test_cia402.py`, with the statusword reaching the FB
up to three cycles late and a following error in CSP. On every scan the simulation records a
violation when the FB:

- sends T9, T16, or bit 7 to a drive it has not seen in Fault, or bit 7 with the enable bits;
- cuts a quick stop short;
- sends Enable operation after `bEnable` fell or while a quick stop holds it down (the
  simulation keeps its own account of that), or bit 4 outside homing before `bValid`;
- enables (T4) or switches mode with an unsafe set-point, or writes 0x6060 before the new
  mode's set-point was safe;
- steps a set-point the enabled drive is following.

The scenarios cover enabling from every state and the way down from every state, both
compared with `cia402.py plan`. They also cover:

- `bEnable` dropped at every scan of the way up, and raised again at every scan of the way down;
- quick stops that end by themselves, ones that stay, and one without 0x6064;
- quick stops asked for: a ramp longer than `tStopTimeout`, a drive that refuses T11, a fault
  or a bad statusword during the stop and while held down, and `bQuickStop`, held and as a
  pulse, at every scan of the way up, of the way down and of a fault reset;
- fault resets that work, ones that fail three times, a level `bReset`, and an acknowledge
  given in Fault reaction active;
- mode switches, including during T4 and in the middle of homing;
- homing, including a result and an error left over from an earlier run;
- the error paths.

Each rule in the list `BROKEN_RULES` is broken on purpose in a copy of the text, and the scenario
named next to it must then fail.

The tests also check that each TwinCAT file holds the same text as the `.st`, with a BOM, CRLF
and a GUID of its own. CI runs `st_review.py --fail-on high` and `tcpou.py check` from a pinned
twincat-st release.

The simulation is the profile's state machine, not a drive. Nothing here was compiled, and none
of it shows what a particular drive does.
