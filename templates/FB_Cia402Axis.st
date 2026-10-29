// FB_Cia402Axis and its types, as plain IEC 61131-3 Structured Text.
// The same declarations and body as the TwinCAT files beside it
// (FB_Cia402Axis.TcPOU and the four .TcDUT); tests/test_templates.py
// fails if the two drift apart. Reviewed and run against a simulated
// drive only: never compiled, never run on a real drive. Read
// templates/README.md first.

{attribute 'qualified_only'}
TYPE E_Cia402State :
(
    NotReadyToSwitchOn  := 0,
    SwitchOnDisabled    := 1,
    ReadyToSwitchOn     := 2,
    SwitchedOn          := 3,
    OperationEnabled    := 4,
    QuickStopActive     := 5,
    FaultReactionActive := 6,
    Fault               := 7,
    Unknown             := 8    // no state; or inputs that cannot be true
) INT;
END_TYPE

{attribute 'qualified_only'}
TYPE E_Cia402Step :
(
    Disabled        := 0,   // switched off, or on the way down
    WaitReady       := 10,  // T1: the drive leaves by itself
    Shutdown        := 11,  // T2: 0x0006
    SwitchOn        := 12,  // T3: 0x0007
    SetMode         := 13,  // 0x6060 written, 0x6061 awaited
    EnableOperation := 14,  // T4: 0x000F
    AbortEnable     := 15,  // bEnable fell during T4: 0x0007, wait
    Homing          := 20,  // controlword bit 4 held high
    Running         := 30,  // bValid: the set-points are the caller's
    ResetLow        := 40,  // bit 7 low, so that the next write is an edge
    ResetEdge       := 41,  // T15: 0x0080
    ResetRelease    := 42,  // bit 7 low again, after every attempt
    ResetPause      := 43,  // before the next attempt
    Error           := 90   // on the way down, waiting for bReset
) INT;
END_TYPE

TYPE ST_Cia402Drive :
STRUCT
    // Drive to PLC (TxPDO): copy in before each call. All three needed.
    nStatusword       : WORD;   // 0x6041
    nModesDisplay     : SINT;   // 0x6061
    nPositionActual   : DINT;   // 0x6064
    // PLC to drive (RxPDO): copy out after each call.
    nControlword      : WORD;   // 0x6040, written by the FB only
    nModesOfOperation : SINT;   // 0x6060, written by the FB only
    nTargetPosition   : DINT;   // 0x607A
    nTargetVelocity   : DINT;   // 0x60FF
    nTargetTorque     : INT;    // 0x6071
    // Caller to FB: controlword bits 4-6, 8, 9, sent only while bValid.
    nModeBits         : WORD;
END_STRUCT
END_TYPE

TYPE ST_Cia402Config :
STRUCT
    tStateTimeout     : TIME := T#2S;     // each transition, the mode switch
    tStopTimeout      : TIME := T#10S;    // each step of the way down
    tHomingTimeout    : TIME := T#60S;    // one whole homing run
    nResetAttempts    : UINT := 3;        // fault resets; 0 counts as 1
    tResetPause       : TIME := T#1S;     // between two reset attempts
    bQuickStopStays   : BOOL := FALSE;    // 0x605A is 5-8 on this drive
    nStandstillWindow : DINT := 0;        // position band, 0x6064 units
    tStandstill       : TIME := T#100MS;  // in the band this long: stopped
END_STRUCT
END_TYPE

FUNCTION_BLOCK FB_Cia402Axis
(*
    One CiA 402 drive: its state machine, the mode of operation, drive-based
    homing and fault reset. From the cia402-motion skill. It is a template:
    reviewed and run against a simulated drive, never compiled, never run
    on a real drive. Test it with reduced torque and speed limits before
    anyone stands near the machine. It is not a safety function: STO, SS1
    and safe stops belong in a safety controller.

    WHEN TO USE IT
    For a drive that makes the motion itself (PP, PV, PT, drive-based
    homing), or a PLC with no motion runtime. Where TwinCAT NC or CODESYS
    SoftMotion can drive the axis, use its axis and the MC_ blocks instead.
    Never both on one drive: both would write 0x6040.

    CONTRACT
    Call it once per cycle, unconditionally, in the task that exchanges the
    drive's process data. Copy 0x6041, 0x6061 and 0x6064 into stDrive
    before the call, in every mode, and stDrive's outputs to the drive
    after it.

    bEnable TRUE    Operation enabled in nMode. Once bValid is TRUE the
                    set-points in stDrive, and nModeBits, are yours.
                    Start a trajectory from where the FB left them: in
                    CSP, from stDrive.nTargetPosition.
    nMode = 6       Home with the method in 0x6098 (write it, and the
                    speeds, by SDO first). bValid then means homed. To
                    home again, drop bEnable or ask for another mode.
                    Change nMode at standstill only.
    bEnable FALSE   Stop and switch off as cia402.py plan <state> sod
                    does: Disable operation (T5: 0x605C decides how the
                    motor stops), then Disable voltage (T10).
    bReset          Rising edge: clear the error. If the drive is in
                    Fault, reset it first: bit 7 low, high, low.

    Enabling always starts from Switch on disabled: a drive found anywhere
    else is taken down first, never taken over as it is. An error takes
    the drive down as bEnable FALSE does, and the FB stays down until
    bReset. If bEnable is still TRUE it then enables again, as PLCopen
    MC_Power does after MC_Reset. nErrorID keeps the first error.

    WHAT IT KEEPS TO (the skill's references/state-machine.md)
    - One command at a time, held until the statusword shows the state it
      leads to, with a timeout. On the way up, any other state is an
      error. If bEnable falls while T4 may still be on its way, the FB
      sends 0x0007 and waits, so that a late T4 is stopped with T5.
    - Fault reset only from Fault: an edge on bit 7, released after every
      attempt, failed ones included. Never bit 7 with the enable bits.
    - Quick stop active is left only when the drive leaves it itself, or,
      where 0x605A keeps it there, at standstill. Never on a timer: that
      state is the stop ramp, and 0x0000 during it lets the motor coast.
    - On the way down, never Operation enabled and never T9.
    - Before T4 the set-points cannot move the motor: 0x607A = 0x6064,
      0x60FF = 0, 0x6071 = 0, bits 4-6, 8, 9 = 0. While the drive is
      enabled and they are not the caller's, the FB leaves them as they
      were, except that a mode switch makes the new mode's set-point safe
      a scan before it writes 0x6060. The mode counts once 0x6061 shows
      it.

    CHECK ON YOUR DRIVE (the skill's references/vendors/)
    - 0x605A 5-8 keeps the drive in Quick stop active at standstill. Set
      stConfig.bQuickStopStays, and nStandstillWindow to the position
      jitter at standstill: the FB then leaves with T12 once the position
      has stayed in the band for tStandstill. Without the flag it waits
      for the drive to leave, which such a drive never does (safe, stuck).
    - Beckhoff's EL72x1 in DS402 reserves statusword bit 5. If it reads 0
      there, Ready to switch on and Switched on match no state, and the
      FB stops with 16#8115 after T2.
    - Statusword bit 12 in CSP is not checked: drives differ on it.
    - A homing result counts only after the drive has shown a phase with
      bits 12 and 13 both 0, from the scan bit 4 goes out on, so that an
      earlier run's result is not taken for this one. A drive that never
      shows one (an instant method 35 or 37 run twice) times out.
*)
VAR_INPUT
    bEnable  : BOOL;              // TRUE: run in nMode; FALSE: stop, off
    nMode    : SINT;              // 0x6060 code: 8 CSP, 1 PP, 6 homing...
    bReset   : BOOL;              // rising edge: clear, reset a fault
    stConfig : ST_Cia402Config;   // timeouts, reset retries, standstill
END_VAR
VAR_OUTPUT
    bValid      : BOOL;           // in nMode: the set-points are yours
    bBusy       : BOOL;           // on the way to what bEnable asks
    bError      : BOOL;
    nErrorID    : UDINT;          // 0 = none, else a cErr code below
    eDriveState : E_Cia402State;  // decoded from 0x6041
END_VAR
VAR_IN_OUT
    stDrive : ST_Cia402Drive;     // this axis' process data
END_VAR
VAR
    eStep            : E_Cia402Step := E_Cia402Step.Disabled;
    eStepPrev        : E_Cia402Step := E_Cia402Step.Disabled;
    eDrivePrev       : E_Cia402State := E_Cia402State.Unknown;
    fbResetTrig      : R_TRIG;
    fbStepTimer      : TON;       // the timeout of the step it is in
    fbStandstill     : TON;
    tStepLimit       : TIME;
    bStepEntered     : BOOL;      // first scan in a new step
    bDriveMoved      : BOOL;      // the decoded state changed this scan
    bDriveSeen       : BOOL;      // the drive has left Not ready
    bMoving          : BOOL;      // position left the standstill band
    nStandstillRef   : DINT;
    bHomingRunSeen   : BOOL;      // bits 12, 13 both 0 since bit 4
    bResetting       : BOOL;      // in one of the fault-reset steps
    bResetRequest    : BOOL;      // bReset rose while in Error
    bSetModeLastScan : BOOL;      // last scan's outputs were SetMode's
    bRunningLastScan : BOOL;      // last scan's outputs were Running's
    nResetCount      : UINT;
END_VAR
VAR CONSTANT
    cModeBits       : WORD := 16#0370;   // controlword bits 4-6, 8, 9
    cResetSettle    : TIME := T#20MS;    // bit 7 low, before and after
    cErrNotReady    : UDINT := 16#8101;  // no Switch on disabled (T1)
    cErrShutdown    : UDINT := 16#8102;  // no Ready to switch on (T2)
    cErrSwitchOn    : UDINT := 16#8103;  // no Switched on (T3)
    cErrEnable      : UDINT := 16#8104;  // no Operation enabled (T4)
    cErrMode        : UDINT := 16#8105;  // 0x6061 never showed nMode
    cErrStop        : UDINT := 16#8106;  // did not get down in time
    cErrHomingTime  : UDINT := 16#8107;  // homing did not end in time
    cErrDriveFault  : UDINT := 16#8110;  // drive in Fault: read 0x603F
    cErrResetFailed : UDINT := 16#8111;  // still in Fault after resets
    cErrQuickStop   : UDINT := 16#8112;  // Quick stop active, not ours
    cErrLeftState   : UDINT := 16#8113;  // drive moved where not asked
    cErrHoming      : UDINT := 16#8114;  // homing error, bit 13
    cErrStatusword  : UDINT := 16#8115;  // 0x6041 decodes to no state
    cErrNoMode      : UDINT := 16#8120;  // nMode = 0
    cErrInvalidStep : UDINT := 16#8FFF;
END_VAR
// 1. Decode 0x6041. Each state has its own mask: bit 5 belongs to four of
//    them and is a don't-care in the other four. A word that matches none
//    is read fault-first, as cia402.py decode sw does.
IF (stDrive.nStatusword AND 16#004F) = 16#0000 THEN
    eDriveState := E_Cia402State.NotReadyToSwitchOn;
ELSIF (stDrive.nStatusword AND 16#004F) = 16#0040 THEN
    eDriveState := E_Cia402State.SwitchOnDisabled;
ELSIF (stDrive.nStatusword AND 16#006F) = 16#0021 THEN
    eDriveState := E_Cia402State.ReadyToSwitchOn;
ELSIF (stDrive.nStatusword AND 16#006F) = 16#0023 THEN
    eDriveState := E_Cia402State.SwitchedOn;
ELSIF (stDrive.nStatusword AND 16#006F) = 16#0027 THEN
    eDriveState := E_Cia402State.OperationEnabled;
ELSIF (stDrive.nStatusword AND 16#006F) = 16#0007 THEN
    eDriveState := E_Cia402State.QuickStopActive;
ELSIF (stDrive.nStatusword AND 16#0008) = 0 THEN
    eDriveState := E_Cia402State.Unknown;
ELSIF (stDrive.nStatusword AND 16#0007) = 16#0007 THEN
    eDriveState := E_Cia402State.FaultReactionActive;
ELSE
    eDriveState := E_Cia402State.Fault;
END_IF

// A drive never goes back to Not ready to switch on. Seen after another
// state, that word means the inputs are not the drive's: a bus restart, a
// copy that never happened. 0x0000 sent then could be T9.
IF (eDriveState <> E_Cia402State.NotReadyToSwitchOn)
   AND (eDriveState <> E_Cia402State.Unknown)
THEN
    bDriveSeen := TRUE;
ELSIF bDriveSeen AND (eDriveState = E_Cia402State.NotReadyToSwitchOn) THEN
    eDriveState := E_Cia402State.Unknown;
END_IF

// 2. Every block that carries state is called here, once per scan, above
//    the state machine that reads it.
fbResetTrig(CLK := bReset);

bStepEntered := (eStep <> eStepPrev);
bDriveMoved  := (eDriveState <> eDrivePrev);
eStepPrev    := eStep;
eDrivePrev   := eDriveState;

// A reset asked for in Error is kept until it can be acted on, so that an
// edge in Fault reaction active is not lost.
IF eStep <> E_Cia402Step.Error THEN
    bResetRequest := FALSE;
ELSIF fbResetTrig.Q THEN
    bResetRequest := TRUE;
END_IF

// The timeout of the step the FB is in. IN low on the scan the step or
// the drive's state changed re-arms it, so every transition gets a full
// timeout of its own.
CASE eStep OF
    E_Cia402Step.Homing:
        tStepLimit := stConfig.tHomingTimeout;
    E_Cia402Step.Disabled, E_Cia402Step.Error:
        tStepLimit := stConfig.tStopTimeout;
    E_Cia402Step.ResetLow, E_Cia402Step.ResetRelease:
        tStepLimit := cResetSettle;
    E_Cia402Step.ResetPause:
        tStepLimit := stConfig.tResetPause;
ELSE
    tStepLimit := stConfig.tStateTimeout;
END_CASE
fbStepTimer(IN := NOT (bStepEntered OR bDriveMoved), PT := tStepLimit);

// Standstill, for leaving Quick stop active where 0x605A keeps the drive
// there: the position has stayed inside the band for tStandstill. It
// measures the motor, not the time since the stop began.
bMoving := ABS(stDrive.nPositionActual - nStandstillRef)
           > stConfig.nStandstillWindow;
IF bMoving THEN
    nStandstillRef := stDrive.nPositionActual;
END_IF
fbStandstill(IN := (eDriveState = E_Cia402State.QuickStopActive)
                   AND NOT bMoving,
             PT := stConfig.tStandstill);

// Homing, statusword bits 13, 12, 10. Bits 12 and 13 both 0 (in progress,
// or not started) cannot be left over from an earlier run. Outside homing
// this follows the latest phase; in it, it latches.
IF (stDrive.nStatusword AND 16#3000) = 0 THEN
    bHomingRunSeen := TRUE;
ELSIF eStep <> E_Cia402Step.Homing THEN
    bHomingRunSeen := FALSE;
END_IF

// 3. A statusword that decodes to no state is an error in every step; a
//    fault is one in every step but the reset itself.
bResetting := (eStep = E_Cia402Step.ResetLow)
              OR (eStep = E_Cia402Step.ResetEdge)
              OR (eStep = E_Cia402Step.ResetRelease)
              OR (eStep = E_Cia402Step.ResetPause);
IF eStep <> E_Cia402Step.Error THEN
    IF eDriveState = E_Cia402State.Unknown THEN
        nErrorID := cErrStatusword;
        eStep    := E_Cia402Step.Error;
    ELSIF NOT bResetting
          AND ((eDriveState = E_Cia402State.Fault)
               OR (eDriveState = E_Cia402State.FaultReactionActive))
    THEN
        nErrorID := cErrDriveFault;
        eStep    := E_Cia402Step.Error;
    END_IF
END_IF

// 4. Transitions. Each step names the state it waits for and the state it
//    may still be in; anything else, or its timeout, is an error.
CASE eStep OF

    E_Cia402Step.Disabled:
        // On the way down (outputs below). Enabling starts only from
        // Switch on disabled, where no command of the way down can still
        // be on its way.
        IF bEnable AND nMode = 0 THEN
            nErrorID := cErrNoMode;
            eStep    := E_Cia402Step.Error;
        ELSIF bEnable
              AND eDriveState = E_Cia402State.NotReadyToSwitchOn
        THEN
            eStep := E_Cia402Step.WaitReady;
        ELSIF bEnable AND eDriveState = E_Cia402State.SwitchOnDisabled THEN
            eStep := E_Cia402Step.Shutdown;
        ELSIF fbStepTimer.Q
              AND ((eDriveState = E_Cia402State.OperationEnabled)
                   OR (eDriveState = E_Cia402State.SwitchedOn)
                   OR (eDriveState = E_Cia402State.ReadyToSwitchOn))
        THEN
            nErrorID := cErrStop;
            eStep    := E_Cia402Step.Error;
        END_IF

    E_Cia402Step.WaitReady:
        IF NOT bEnable THEN
            eStep := E_Cia402Step.Disabled;
        ELSIF eDriveState = E_Cia402State.SwitchOnDisabled THEN
            eStep := E_Cia402Step.Shutdown;
        ELSIF eDriveState <> E_Cia402State.NotReadyToSwitchOn THEN
            nErrorID := cErrLeftState;
            eStep    := E_Cia402Step.Error;
        ELSIF fbStepTimer.Q THEN
            nErrorID := cErrNotReady;
            eStep    := E_Cia402Step.Error;
        END_IF

    E_Cia402Step.Shutdown:
        IF NOT bEnable THEN
            eStep := E_Cia402Step.Disabled;
        ELSIF eDriveState = E_Cia402State.ReadyToSwitchOn THEN
            eStep := E_Cia402Step.SwitchOn;
        ELSIF eDriveState <> E_Cia402State.SwitchOnDisabled THEN
            nErrorID := cErrLeftState;
            eStep    := E_Cia402Step.Error;
        ELSIF fbStepTimer.Q THEN
            nErrorID := cErrShutdown;
            eStep    := E_Cia402Step.Error;
        END_IF

    E_Cia402Step.SwitchOn:
        IF NOT bEnable THEN
            eStep := E_Cia402Step.Disabled;
        ELSIF eDriveState = E_Cia402State.SwitchedOn THEN
            eStep := E_Cia402Step.SetMode;
        ELSIF eDriveState <> E_Cia402State.ReadyToSwitchOn THEN
            nErrorID := cErrLeftState;
            eStep    := E_Cia402Step.Error;
        ELSIF fbStepTimer.Q THEN
            nErrorID := cErrSwitchOn;
            eStep    := E_Cia402Step.Error;
        END_IF

    E_Cia402Step.SetMode:
        // In Switched on on the way up, in Operation enabled when the mode
        // changes while running; the drive must stay where it was. Done
        // once 0x6060 has gone out as nMode and 0x6061 shows it.
        IF NOT bEnable THEN
            eStep := E_Cia402Step.Disabled;
        ELSIF nMode = 0 THEN
            nErrorID := cErrNoMode;
            eStep    := E_Cia402Step.Error;
        ELSIF eDriveState = E_Cia402State.QuickStopActive THEN
            nErrorID := cErrQuickStop;
            eStep    := E_Cia402Step.Error;
        ELSIF bDriveMoved
              OR ((eDriveState <> E_Cia402State.SwitchedOn)
                  AND (eDriveState <> E_Cia402State.OperationEnabled))
        THEN
            nErrorID := cErrLeftState;
            eStep    := E_Cia402Step.Error;
        ELSIF (stDrive.nModesOfOperation = nMode)
              AND (stDrive.nModesDisplay = nMode)
        THEN
            IF eDriveState = E_Cia402State.SwitchedOn THEN
                eStep := E_Cia402Step.EnableOperation;
            ELSIF nMode = 6 THEN
                eStep := E_Cia402Step.Homing;
            ELSE
                eStep := E_Cia402Step.Running;
            END_IF
        ELSIF fbStepTimer.Q THEN
            nErrorID := cErrMode;
            eStep    := E_Cia402Step.Error;
        END_IF

    E_Cia402Step.EnableOperation:
        IF eDriveState = E_Cia402State.OperationEnabled THEN
            IF NOT bEnable THEN
                eStep := E_Cia402Step.Disabled;
            ELSIF (nMode <> stDrive.nModesOfOperation)
                  OR (nMode <> stDrive.nModesDisplay)
            THEN
                eStep := E_Cia402Step.SetMode;
            ELSIF nMode = 6 THEN
                eStep := E_Cia402Step.Homing;
            ELSE
                eStep := E_Cia402Step.Running;
            END_IF
        ELSIF eDriveState <> E_Cia402State.SwitchedOn THEN
            nErrorID := cErrLeftState;
            eStep    := E_Cia402Step.Error;
        ELSIF NOT bEnable THEN
            eStep := E_Cia402Step.AbortEnable;
        ELSIF fbStepTimer.Q THEN
            nErrorID := cErrEnable;
            eStep    := E_Cia402Step.Error;
        END_IF

    E_Cia402Step.AbortEnable:
        // 0x000F may still be on its way, and 0x0000 would then be T9.
        // 0x0007 is T5 in Operation enabled and nothing in Switched on;
        // after tStateTimeout in Switched on no T4 can still come.
        IF (eDriveState <> E_Cia402State.SwitchedOn) OR fbStepTimer.Q THEN
            eStep := E_Cia402Step.Disabled;
        END_IF

    E_Cia402Step.Homing:
        // Dropping bit 4 interrupts the run: bEnable FALSE and a mode
        // change both do that, through the outputs of the next step.
        IF NOT bEnable THEN
            eStep := E_Cia402Step.Disabled;
        ELSIF eDriveState = E_Cia402State.QuickStopActive THEN
            nErrorID := cErrQuickStop;
            eStep    := E_Cia402Step.Error;
        ELSIF eDriveState <> E_Cia402State.OperationEnabled THEN
            nErrorID := cErrLeftState;
            eStep    := E_Cia402Step.Error;
        ELSIF (nMode <> stDrive.nModesOfOperation)
              OR (nMode <> stDrive.nModesDisplay)
        THEN
            eStep := E_Cia402Step.SetMode;
        ELSIF bHomingRunSeen
              AND ((stDrive.nStatusword AND 16#2000) <> 0)
        THEN
            nErrorID := cErrHoming;
            eStep    := E_Cia402Step.Error;
        ELSIF bHomingRunSeen
              AND ((stDrive.nStatusword AND 16#3400) = 16#1400)
        THEN
            eStep := E_Cia402Step.Running;
        ELSIF fbStepTimer.Q THEN
            nErrorID := cErrHomingTime;
            eStep    := E_Cia402Step.Error;
        END_IF

    E_Cia402Step.Running:
        IF NOT bEnable THEN
            eStep := E_Cia402Step.Disabled;
        ELSIF eDriveState = E_Cia402State.QuickStopActive THEN
            nErrorID := cErrQuickStop;
            eStep    := E_Cia402Step.Error;
        ELSIF eDriveState <> E_Cia402State.OperationEnabled THEN
            nErrorID := cErrLeftState;
            eStep    := E_Cia402Step.Error;
        ELSIF (nMode <> stDrive.nModesOfOperation)
              OR (nMode <> stDrive.nModesDisplay)
        THEN
            eStep := E_Cia402Step.SetMode;
        END_IF

    E_Cia402Step.ResetLow:
        IF fbStepTimer.Q AND eDriveState = E_Cia402State.Fault THEN
            eStep := E_Cia402Step.ResetEdge;
        END_IF

    E_Cia402Step.ResetEdge:
        // Hold the edge until the drive leaves Fault or the timeout, then
        // release bit 7 either way.
        IF (eDriveState <> E_Cia402State.Fault) OR fbStepTimer.Q THEN
            eStep := E_Cia402Step.ResetRelease;
        END_IF

    E_Cia402Step.ResetRelease:
        IF fbStepTimer.Q THEN
            IF eDriveState = E_Cia402State.SwitchOnDisabled THEN
                nErrorID := 0;
                eStep    := E_Cia402Step.Disabled;
            ELSIF (eDriveState <> E_Cia402State.Fault)
                  AND (eDriveState <> E_Cia402State.FaultReactionActive)
            THEN
                nErrorID := cErrLeftState;
                eStep    := E_Cia402Step.Error;
            ELSE
                // Still faulted: the cause is still there. Read 0x603F.
                nResetCount := nResetCount + 1;
                IF nResetCount < stConfig.nResetAttempts THEN
                    eStep := E_Cia402Step.ResetPause;
                ELSE
                    nErrorID := cErrResetFailed;
                    eStep    := E_Cia402Step.Error;
                END_IF
            END_IF
        END_IF

    E_Cia402Step.ResetPause:
        IF fbStepTimer.Q AND eDriveState = E_Cia402State.Fault THEN
            eStep := E_Cia402Step.ResetEdge;
        END_IF

    E_Cia402Step.Error:
        // On the way down, as Disabled. A reset waits while the drive is
        // in Fault reaction active or its statusword decodes to nothing.
        IF bResetRequest THEN
            IF eDriveState = E_Cia402State.Fault THEN
                nErrorID    := 0;
                nResetCount := 0;
                eStep       := E_Cia402Step.ResetLow;
            ELSIF (eDriveState <> E_Cia402State.FaultReactionActive)
                  AND (eDriveState <> E_Cia402State.Unknown)
            THEN
                nErrorID := 0;
                eStep    := E_Cia402Step.Disabled;
            END_IF
        END_IF

ELSE
    nErrorID := cErrInvalidStep;
    eStep    := E_Cia402Step.Error;
END_CASE

// 5. Outputs, from the step the FB is in after this scan's transitions:
//    the word sent always belongs to the step that holds it.
CASE eStep OF

    E_Cia402Step.Disabled, E_Cia402Step.Error:
        // The way down: one word per state, as cia402.py plan <state> sod.
        CASE eDriveState OF
            E_Cia402State.OperationEnabled:
                stDrive.nControlword := 16#0007;   // T5, stops as 0x605C
            E_Cia402State.QuickStopActive:
                IF stConfig.bQuickStopStays AND fbStandstill.Q THEN
                    stDrive.nControlword := 16#0000;   // T12, stopped
                ELSE
                    stDrive.nControlword := 16#0002;   // let it finish
                END_IF
            E_Cia402State.Fault, E_Cia402State.FaultReactionActive:
                stDrive.nControlword := 16#0000;   // bit 7 low
            E_Cia402State.Unknown:
                // Keep the last word, less enable operation, the mode bits
                // and bit 7: it cannot enable, and it cannot cut power.
                stDrive.nControlword := stDrive.nControlword AND 16#0007;
        ELSE
            stDrive.nControlword := 16#0000;   // T10, T7, or at rest
        END_CASE

    E_Cia402Step.WaitReady, E_Cia402Step.ResetLow,
    E_Cia402Step.ResetRelease, E_Cia402Step.ResetPause:
        stDrive.nControlword := 16#0000;

    E_Cia402Step.Shutdown:
        stDrive.nControlword := 16#0006;   // T2

    E_Cia402Step.SwitchOn, E_Cia402Step.AbortEnable:
        stDrive.nControlword := 16#0007;   // T3; or T5 after a late T4

    E_Cia402Step.SetMode:
        IF eDriveState = E_Cia402State.OperationEnabled THEN
            stDrive.nControlword := 16#000F;   // hold Operation enabled
        ELSE
            stDrive.nControlword := 16#0007;   // hold Switched on
        END_IF
        IF bSetModeLastScan THEN
            stDrive.nModesOfOperation := nMode;
        END_IF

    E_Cia402Step.EnableOperation:
        stDrive.nControlword := 16#000F;   // T4

    E_Cia402Step.Homing:
        stDrive.nControlword := 16#001F;   // bit 4: homing start, held

    E_Cia402Step.Running:
        // The caller's bits from the second scan on: on the first, the
        // caller has not seen bValid yet.
        IF (nMode = 6) OR NOT bRunningLastScan THEN
            stDrive.nControlword := 16#000F;
        ELSE
            stDrive.nControlword := 16#000F
                                    OR (stDrive.nModeBits AND cModeBits);
        END_IF

    E_Cia402Step.ResetEdge:
        // T15, a rising edge on bit 7: only ever sent to a drive in Fault.
        IF eDriveState = E_Cia402State.Fault THEN
            stDrive.nControlword := 16#0080;
        ELSE
            stDrive.nControlword := 16#0000;
        END_IF

ELSE
    stDrive.nControlword := 16#0000;
END_CASE
bSetModeLastScan := (eStep = E_Cia402Step.SetMode);
bRunningLastScan := (eStep = E_Cia402Step.Running);

// 6. Set-points. From bValid on they are the caller's. Without torque the
//    FB holds them where enabling cannot move the motor. With the drive
//    enabled it leaves them as they were, so that it never steps one the
//    drive is following; a mode switch makes the new mode's set-point
//    safe. The caller's mode bits are cleared until bValid.
IF eStep = E_Cia402Step.Running THEN
    ;
ELSIF (eDriveState <> E_Cia402State.OperationEnabled)
      AND (eDriveState <> E_Cia402State.QuickStopActive)
THEN
    stDrive.nTargetPosition := stDrive.nPositionActual;
    stDrive.nTargetVelocity := 0;
    stDrive.nTargetTorque   := 0;
    stDrive.nModeBits       := 0;
ELSE
    IF eStep = E_Cia402Step.SetMode THEN
        CASE nMode OF
            1, 8:
                stDrive.nTargetPosition := stDrive.nPositionActual;
            3, 9:
                stDrive.nTargetVelocity := 0;
            4, 10, 11:
                stDrive.nTargetTorque := 0;
        ELSE
            ;   // a mode of the drive's own: see its manual
        END_CASE
    END_IF
    stDrive.nModeBits := 0;
END_IF

bValid := (eStep = E_Cia402Step.Running);
bError := (eStep = E_Cia402Step.Error);
bBusy  := NOT bValid AND NOT bError
          AND (bEnable
               OR ((eDriveState <> E_Cia402State.SwitchOnDisabled)
                   AND (eDriveState <> E_Cia402State.NotReadyToSwitchOn)));
END_FUNCTION_BLOCK
