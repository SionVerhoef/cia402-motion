# Templates

`FB_Cia402Axis` is a PLC function block for one CiA 402 drive. It brings the drive through its
state machine into Operation enabled in the mode you ask for, homes it, switches modes, takes
it down again, and resets faults, keeping to the rules in `../references/state-machine.md`.

> **Status: reviewed, not run.** twincat-st's `st_review.py` reports no findings, and
> `tests/test_templates.py` runs the FB's own text against a simulated drive. It has never been
> compiled in TwinCAT or CODESYS, and it has never driven a real drive. Test it with reduced
> torque and speed limits before anyone stands near the machine. It is not a safety function:
> STO, SS1 and safe stops belong in a safety controller (`../references/safety-boundary.md`).

## Files

| File | What |
|---|---|
| `FB_Cia402Axis.TcPOU` | The function block, TwinCAT 3 format (UTF-8 with BOM, CRLF) |
| `E_Cia402State.TcDUT` | The drive's state, decoded from the statusword |
| `E_Cia402Step.TcDUT` | The FB's own steps |
| `ST_Cia402Drive.TcDUT` | One axis' process data: what goes to and comes from the drive |
| `ST_Cia402Config.TcDUT` | Timeouts, reset retries, the standstill band |
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
| `nMode` | SINT in | The 0x6060 code. 6 means home: `bValid` then says homed |
| `bReset` | BOOL in | Rising edge: clear the error; from Fault, run the reset first |
| `stConfig` | `ST_Cia402Config` in | The defaults are in the type |
| `bValid` | BOOL out | Enabled in `nMode`: the set-points in `stDrive` are yours |
| `bBusy` | BOOL out | On the way to what `bEnable` asks |
| `bError`, `nErrorID` | out | The error codes are below |
| `eDriveState` | `E_Cia402State` out | For an HMI or a diagnosis |
| `stDrive` | `ST_Cia402Drive` in-out | Fill its inputs before the call, send its outputs after |

Until `bValid` the FB holds 0x607A at 0x6064, 0x60FF and 0x6071 at 0, and controlword bits 4–6,
8 and 9 at 0. From `bValid` on, write your set-points and `stDrive.nModeBits` (the PP handshake,
halt). Start a CSP trajectory from `stDrive.nTargetPosition`, where the FB left it.

An error takes the drive down the way `bEnable` FALSE does, and the FB stays down until `bReset`.
With `bEnable` still TRUE it then enables again, as PLCopen `MC_Power` does after `MC_Reset`.

| `nErrorID` | Meaning |
|---|---|
| 16#8101–16#8104 | The drive did not take T1, T2, T3 or T4 in `tStateTimeout` |
| 16#8105 | 0x6061 never showed `nMode`: the drive may not have the mode (0x6502) |
| 16#8106 | The way down did not end in `tStopTimeout` |
| 16#8107 | Homing did not end in `tHomingTimeout` |
| 16#8110 | The drive is in Fault: read 0x603F |
| 16#8111 | Still in Fault after `nResetAttempts` resets: the cause is still there |
| 16#8112 | Quick stop active, not asked for by the FB |
| 16#8113 | The drive left the state the FB was holding (Operation enabled, say) |
| 16#8114 | Homing error, statusword bit 13 |
| 16#8115 | The statusword matches no state, and its fault bit is 0 |
| 16#8120 | `nMode` is 0 |

## Wiring it, in TwinCAT

```
VAR
    fbAxis1   : FB_Cia402Axis;
    stAxis1   : ST_Cia402Drive;
    stConfig1 : ST_Cia402Config;
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
fbAxis1(bEnable := bAxis1On, nMode := 8, bReset := bAcknowledge,
        stConfig := stConfig1, stDrive := stAxis1);
IF fbAxis1.bValid THEN
    stAxis1.nTargetPosition := nTrajectory1;   // started from where the FB left it
END_IF
nControl1 := WORD_TO_UINT(stAxis1.nControlword);
nModeOut1 := stAxis1.nModesOfOperation;
nTarget1  := stAxis1.nTargetPosition;
```

Call it in the task that exchanges the drive's process data, once per cycle. Copy only the members
your mapping has. For homing, write 0x6098 and the speeds 0x6099 by SDO before asking for mode 6.

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
write the mode by SDO at start-up and copy 0x6061 into `stDrive.nModesDisplay`, or the FB
waits for a mode it cannot see and stops with 16#8105.

## How it was tested

`tests/st_subset.py` runs the Structured Text subset these files are written in, and refuses
anything else. `tests/test_templates.py` runs `FB_Cia402Axis.st` with it, against a simulated
drive built on the model drive in `tests/test_cia402.py`. On every scan the simulation records a
violation when the FB breaks a rule: T9, bit 7 outside Fault or with the enable bits, a quick stop
cut short, T16, Operation enabled while `bEnable` is FALSE, a CSP jump on enable or on a mode
switch, 0x6060 written before the set-points were safe. Scenarios cover enabling from every
state, the way down, quick stops that end by themselves and ones that stay, fault resets that
work and ones that fail three times, mode switches, homing, and the error paths. The transitions
the drive takes are compared with `cia402.py plan`. Each rule was also broken on purpose, once,
to see a test fail.

The tests also check that each TwinCAT file holds the same text as the `.st`, with a BOM, CRLF
and a GUID of its own. CI runs `st_review.py --fail-on high` and `tcpou.py check` from a pinned
twincat-st release.

The simulation is the profile's state machine, not a drive. It cannot show what a particular
drive does: check the vendor list in the FB's header comment on yours.
