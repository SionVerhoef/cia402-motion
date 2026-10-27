// FB_Cia402Axis and its types, as plain IEC 61131-3 Structured Text.
// The same declarations and body as the TwinCAT files beside it
// (FB_Cia402Axis.TcPOU and the three .TcDUT); tests/test_templates.py
// fails if the two drift apart. Reviewed and run in a simulation only:
// it has never driven a real drive. Read templates/README.md first.

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
    Unknown             := 8    // matches no state, and the fault bit is 0
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
    // Drive to PLC (TxPDO): copy in, or link, before each call.
    nStatusword       : WORD;   // 0x6041
    nModesDisplay     : SINT;   // 0x6061
    nPositionActual   : DINT;   // 0x6064
    // PLC to drive (RxPDO): copy out, or link, after each call.
    nControlword      : WORD;   // 0x6040, written by the FB only
    nModesOfOperation : SINT;   // 0x6060, written by the FB only
    nTargetPosition   : DINT;   // 0x607A, held at 0x6064 until bValid
    nTargetVelocity   : DINT;   // 0x60FF, held at 0 until bValid
    nTargetTorque     : INT;    // 0x6071, held at 0 until bValid
    // Caller to FB.
    nModeBits         : WORD;   // controlword bits 4-6, 8, 9 while bValid
END_STRUCT
END_TYPE

TYPE ST_Cia402Config :
STRUCT
    tStateTimeout     : TIME := T#2S;     // each transition, the mode switch
    tStopTimeout      : TIME := T#10S;    // the stop from Operation enabled
    tHomingTimeout    : TIME := T#60S;    // one whole homing run
    nResetAttempts    : UINT := 3;        // fault resets before giving up
    tResetPause       : TIME := T#1S;     // between two reset attempts
    nStandstillWindow : DINT := 0;        // position band, 0x6064 units
    tStandstill       : TIME := T#100MS;  // in the band this long: stopped
END_STRUCT
END_TYPE

FUNCTION_BLOCK FB_Cia402Axis
(*
    One CiA 402 drive: its state machine, the mode of operation, drive-based
    homing and fault reset. From the cia402-motion skill. It is a template:
    reviewed and run against a simulated drive, never against a real one.
    Test it with reduced torque and speed limits before anyone stands near
    the machine. It is not a safety function: STO, SS1 and safe stops
    belong in a safety controller.

    CONTRACT
    Call it once per cycle, unconditionally, in the task that exchanges the
    drive's process data. stDrive is that data: inputs in before the call,
    outputs out after it.

    bEnable TRUE    Operation enabled in nMode. Once bValid is TRUE the
                    set-points in stDrive are yours, and nModeBits too.
                    Start a CSP trajectory from stDrive.nTargetPosition:
                    the FB left it at the actual position.
    nMode = 6       Home with the method in 0x6098 (write it, and the
                    speeds, by SDO first). bValid then means homed. To
                    home again, drop bEnable or ask for another mode.
    bEnable FALSE   Stop and switch off as cia402.py plan <state> sod
                    does: Disable operation (T5: 0x605C decides how the
                    motor stops), then Disable voltage (T10).
    bReset          Rising edge: clear the error. If the drive is in
                    Fault, reset it first: bit 7 low, high, low.

    An error takes the drive down as bEnable FALSE does, and the FB stays
    down until bReset. If bEnable is still TRUE it then enables again, as
    PLCopen MC_Power does after MC_Reset. A drive found in Operation
    enabled is taken down to Switched on first, never adopted as it is.

    WHAT IT KEEPS TO (references/state-machine.md)
    - One command at a time, held until the statusword shows the state it
      leads to, with a timeout. Any other state is an error.
    - Fault reset only from Fault: an edge on bit 7, released after every
      attempt, failed ones included. Never bit 7 with the enable bits.
    - Quick stop active is left only when the drive leaves it itself, or
      at standstill. Never on a timer: that state is the stop ramp, and
      0x0000 in the middle of it lets the motor coast.
    - On the way down, never Operation enabled, and never T9.
    - The set-points are safe before T4 and for a scan before every 0x6060
      write: 0x607A = 0x6064, 0x60FF = 0, 0x6071 = 0, bits 4-6, 8, 9 = 0.
      A mode counts only once 0x6061 shows it.

    CHECK ON YOUR DRIVE (references/vendors/)
    - 0x605A 5-8 keeps the drive in Quick stop active at standstill. The
      FB then leaves with T12 once the position has stayed inside
      stConfig.nStandstillWindow for tStandstill. The default band is 0:
      on an encoder that jitters at standstill, set it, or the FB holds
      the quick stop for ever (safe, but stuck).
    - Drives without quick stop: Beckhoff's EL72x1 in DS402 reserves
      statusword bit 5. If it reads 0 in Operation enabled, this FB sees
      Quick stop active instead.
    - Statusword bit 12 in CSP is not checked: drives differ on it.
    - Homing is done on bits 12 and 10, counted only after the drive has
      shown another phase since bit 4 rose, so that the result of an
      earlier run is not taken for this one. A drive that never shows one
      (an instant method 35 or 37 run twice) times out instead.
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
    eStep          : E_Cia402Step := E_Cia402Step.Disabled;
    eStepPrev      : E_Cia402Step := E_Cia402Step.Disabled;
    eDrivePrev     : E_Cia402State := E_Cia402State.Unknown;
    fbResetTrig    : R_TRIG;
    fbStepTimer    : TON;         // the timeout of the step it is in
    fbStandstill   : TON;
    tStepLimit     : TIME;
    bStepEntered   : BOOL;        // first scan in a new step
    bDriveMoved    : BOOL;        // the decoded state changed this scan
    bMoving        : BOOL;        // position left the standstill band
    nStandstillRef : DINT;
    bHomingRunSeen : BOOL;        // a phase other than done, since bit 4
    bResetting     : BOOL;        // in one of the fault-reset steps
    bHeldLastScan  : BOOL;        // set-points were the FB's last scan
    nResetCount    : UINT;
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
    cErrLeftState   : UDINT := 16#8113;  // drive left the state held
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

// 2. Every block that carries state is called here, once per scan, above
//    the state machine that reads it.
fbResetTrig(CLK := bReset);

bStepEntered := (eStep <> eStepPrev);
bDriveMoved  := (eDriveState <> eDrivePrev);
eStepPrev    := eStep;
eDrivePrev   := eDriveState;

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

// Homing phase, statusword bits 13, 12, 10. Outside homing this tracks
// the latest phase; in it, it latches once a phase other than done shows.
IF (stDrive.nStatusword AND 16#3400) <> 16#1400 THEN
    bHomingRunSeen := TRUE;
ELSIF eStep <> E_Cia402Step.Homing THEN
    bHomingRunSeen := FALSE;
END_IF

// 3. A fault is an error in every step but the reset itself; so is a
//    statusword that decodes to no state.
bResetting := (eStep = E_Cia402Step.ResetLow)
              OR (eStep = E_Cia402Step.ResetEdge)
              OR (eStep = E_Cia402Step.ResetRelease)
              OR (eStep = E_Cia402Step.ResetPause);
IF NOT bResetting AND eStep <> E_Cia402Step.Error THEN
    IF (eDriveState = E_Cia402State.Fault)
       OR (eDriveState = E_Cia402State.FaultReactionActive)
    THEN
        nErrorID := cErrDriveFault;
        eStep    := E_Cia402Step.Error;
    ELSIF eDriveState = E_Cia402State.Unknown THEN
        nErrorID := cErrStatusword;
        eStep    := E_Cia402Step.Error;
    END_IF
END_IF

// 4. Transitions. Each step names the state it waits for and the state it
//    may still be in; anything else, or its timeout, is an error.
CASE eStep OF

    E_Cia402Step.Disabled:
        // On the way down (outputs below). From Operation enabled and
        // Quick stop active the way down goes on even with bEnable TRUE.
        IF bEnable AND nMode = 0 THEN
            nErrorID := cErrNoMode;
            eStep    := E_Cia402Step.Error;
        ELSIF bEnable
              AND eDriveState = E_Cia402State.NotReadyToSwitchOn
        THEN
            eStep := E_Cia402Step.WaitReady;
        ELSIF bEnable AND eDriveState = E_Cia402State.SwitchOnDisabled THEN
            eStep := E_Cia402Step.Shutdown;
        ELSIF bEnable AND eDriveState = E_Cia402State.ReadyToSwitchOn THEN
            eStep := E_Cia402Step.SwitchOn;
        ELSIF bEnable AND eDriveState = E_Cia402State.SwitchedOn THEN
            eStep := E_Cia402Step.SetMode;
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
        // changes while running. Done once 0x6060 has gone out as nMode
        // and 0x6061 shows it.
        IF NOT bEnable THEN
            eStep := E_Cia402Step.Disabled;
        ELSIF nMode = 0 THEN
            nErrorID := cErrNoMode;
            eStep    := E_Cia402Step.Error;
        ELSIF eDriveState = E_Cia402State.QuickStopActive THEN
            nErrorID := cErrQuickStop;
            eStep    := E_Cia402Step.Error;
        ELSIF (eDriveState <> E_Cia402State.SwitchedOn)
              AND (eDriveState <> E_Cia402State.OperationEnabled)
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
        IF NOT bEnable THEN
            eStep := E_Cia402Step.Disabled;
        ELSIF eDriveState = E_Cia402State.OperationEnabled THEN
            IF nMode = 6 THEN
                eStep := E_Cia402Step.Homing;
            ELSE
                eStep := E_Cia402Step.Running;
            END_IF
        ELSIF eDriveState <> E_Cia402State.SwitchedOn THEN
            nErrorID := cErrLeftState;
            eStep    := E_Cia402Step.Error;
        ELSIF fbStepTimer.Q THEN
            nErrorID := cErrEnable;
            eStep    := E_Cia402Step.Error;
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
        ELSIF (stDrive.nStatusword AND 16#2000) <> 0 THEN
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
        IF fbStepTimer.Q THEN
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
        IF fbStepTimer.Q THEN
            eStep := E_Cia402Step.ResetEdge;
        END_IF

    E_Cia402Step.Error:
        // On the way down, as Disabled. Fault reset only from Fault; in
        // Fault reaction active, wait for Fault and reset again.
        IF fbResetTrig.Q THEN
            IF eDriveState = E_Cia402State.Fault THEN
                nErrorID    := 0;
                nResetCount := 0;
                eStep       := E_Cia402Step.ResetLow;
            ELSIF eDriveState <> E_Cia402State.FaultReactionActive THEN
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
                IF fbStandstill.Q THEN
                    stDrive.nControlword := 16#0000;   // T12, stopped
                ELSE
                    stDrive.nControlword := 16#0002;   // let it finish
                END_IF
            E_Cia402State.Fault, E_Cia402State.FaultReactionActive:
                stDrive.nControlword := 16#0000;   // bit 7 low
            E_Cia402State.Unknown:
                ;   // hold the last word until 0x6041 decodes again
        ELSE
            stDrive.nControlword := 16#0000;   // T10, T7, or at rest
        END_CASE

    E_Cia402Step.WaitReady, E_Cia402Step.ResetLow,
    E_Cia402Step.ResetRelease, E_Cia402Step.ResetPause:
        stDrive.nControlword := 16#0000;

    E_Cia402Step.Shutdown:
        stDrive.nControlword := 16#0006;   // T2

    E_Cia402Step.SwitchOn:
        stDrive.nControlword := 16#0007;   // T3

    E_Cia402Step.SetMode:
        IF eDriveState = E_Cia402State.OperationEnabled THEN
            stDrive.nControlword := 16#000F;   // hold Operation enabled
        ELSE
            stDrive.nControlword := 16#0007;   // hold Switched on
        END_IF
        IF bHeldLastScan THEN
            stDrive.nModesOfOperation := nMode;
        END_IF

    E_Cia402Step.EnableOperation:
        stDrive.nControlword := 16#000F;   // T4

    E_Cia402Step.Homing:
        stDrive.nControlword := 16#001F;   // bit 4: homing start, held

    E_Cia402Step.Running:
        IF nMode = 6 THEN
            stDrive.nControlword := 16#000F;   // homed: bit 4 low again
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

// 6. Until bValid the FB holds the set-points where they cannot move the
//    motor; from then on they are the caller's.
IF eStep <> E_Cia402Step.Running THEN
    stDrive.nTargetPosition := stDrive.nPositionActual;
    stDrive.nTargetVelocity := 0;
    stDrive.nTargetTorque   := 0;
END_IF
bHeldLastScan := (eStep <> E_Cia402Step.Running);

bValid := (eStep = E_Cia402Step.Running);
bError := (eStep = E_Cia402Step.Error);
bBusy  := NOT bValid AND NOT bError
          AND (bEnable
               OR ((eDriveState <> E_Cia402State.SwitchOnDisabled)
                   AND (eDriveState <> E_Cia402State.NotReadyToSwitchOn)));
END_FUNCTION_BLOCK
