# Bench test: the first run of FB_Cia402Axis on a drive

`FB_Cia402Axis` has been reviewed and simulated, never compiled and never run on a drive
(`README.md`, Status). This is the protocol for its first run: compile it, run one drive
through every scenario below at reduced limits, and record what matched the simulation.
Run it again for each new drive family.

The scenarios are ordered so that nothing moves before the steps without motion have passed.
Stop at the first one that does not do what it says, record it, and fix or file it before going
on.

## 1. Compile, before any drive

1. Make a TwinCAT 3 PLC project (4024 or later) and add the five files from this folder. To
   give them fresh GUIDs, create each object with twincat-st's `tcpou.py new` and copy the
   source in with `tcpou.py set` (`README.md`, Files). Register them with `tcpou.py register`.
2. Build without XAE open, from the twincat-st repository:

   ```
   powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts\xae_build.ps1 -Solution <x.sln>
   ```

   Exit code 0 means every project built. Keep the compiler output.
3. Fix what the compiler rejects in `FB_Cia402Axis.st` and push the change to the TwinCAT files
   with `tcpou.py set`; `tests/test_templates.py` checks that the two agree. Rerun the tests. A
   fix that changes behaviour needs a test that would have caught it.

## 2. The bench

- **STO wired in hardware**, and tested: STO open must take torque off whatever the PLC
  sends. An E-stop within reach. Nothing in this FB is a safety function.
- **Motor uncoupled**, or coupled only to a load that can do no harm at full speed.
- **Limits set in the drive**, in its startup list or by SDO, so that a wrong word cannot
  do much: max torque 0x6072, max motor speed 0x6080, following-error window 0x6065, and
  software position limits 0x607D if the drive has them. Low values, well below the motor's
  rating.
- **Stop behaviour known**: read 0x605A, 0x605B, 0x605C and 0x605E, and look the drive up in
  `../references/vendors/` (by name, or by 0x1018 vendor ID).

## 3. The drive and the FB

- Read 0x6502 (supported modes) and 0x100A (firmware). Map the objects of `README.md`, PDO
  mapping, and check the mapping with `cia402.py pdo`.
- Set `ST_Cia402Config` for this drive: `bQuickStopStays` and `nStandstillWindow` if 0x605A is
  5–8; the timeouts if the drive is slower than the defaults.
- Wire the FB as in `README.md`, Wiring it, with `bInputsValid` from WcState and the slave
  state. Call it once per cycle in the task that exchanges the drive's process data.

## 4. Recording

Record every scenario with TwinCAT Scope at the task cycle: `stAxis1.nControlword`,
`nStatusword`, `nModesOfOperation`, `nModesDisplay`, `nPositionActual`, `nTargetPosition`, and
`fbAxis1.bValid`, `bBusy`, `bError`, `nErrorID`. Export each recording to CSV and run:

```
python3 scripts/cia402.py trace scenario.csv
```

It lists each state change with its transition number, and flags where the master breaks
`../references/state-machine.md`. **Any error it reports is a bug in the FB or a drive that
departs from the profile.** Record which. Keep the CSV files outside the repository.

The baseline: scenarios 1–3, 5–7, 9 and 10, run against the simulated drive of
`tests/test_templates.py` and written out as such a CSV, trace with no error and no warning,
and one note for the fault in 6.

## 5. Scenarios

Words are the controlwords the FB sends, repeats left out. "Then" means the next word waits for
the statusword to confirm the one before. Skip 9–11 on a drive without homing (no 6 in 0x6502,
as on a Beckhoff EL72x1). Scenario 7 is the default since PR #52; with
`stConfig.bEnableAfterReset` TRUE the FB re-enables after the reset instead.

| # | Do | Expect | Motion |
|---|---|---|---|
| 1 | Bus to OP, `bEnable` FALSE | 0x0000; `eDriveState` Switch on disabled; `bBusy`, `bValid`, `bError` FALSE | none |
| 2 | `bEnable` TRUE, `nMode` 8 (CSP), no trajectory | 0x0006, then 0x0007, then 0x000F (T2, T3, T4); 0x6060 = 8 and 0x6061 = 8 before 0x000F; 0x607A = 0x6064 throughout; `bValid` TRUE | none: the motor holds, no jump |
| 3 | `bEnable` FALSE | 0x0007 (T5), then 0x0002 to Switch on disabled, then 0x0000 once `tStateTimeout` has passed with no bit 3 sent; the motor stops as 0x605C says | none |
| 4 | Enable as in 2, then move the target a few hundred increments in small steps | `bValid` stays TRUE; the trajectory starts from the target the FB left on the rising edge of `bValid` | small |
| 5 | `bQuickStop` TRUE for one scan, at standstill, then while moving as in 4 | 0x0002 at once and held (T11); Quick stop active, then Switch on disabled (0x605A 0–4), or held at standstill and left with T12 (5–8, with `bQuickStopStays`); `bError` FALSE. `bEnable` TRUE does not restart it: drop `bEnable`, then raise it | small |
| 6 | Make the drive fault, safely: a following-error window 0x6065 of a few increments and a small move, or the drive's own test fault | `bError`, 16#8110, `eDriveState` Fault; read 0x603F and look it up for that vendor | small |
| 7 | Clear the cause, then `bReset` | 0x0000, then 0x0080 held until the drive leaves Fault, then 0x0000; Switch on disabled. **The FB stays down** with `bEnable` TRUE: drop `bEnable` and raise it, and it enables as in 2 | none |
| 8 | Fault again, leave the cause, `bReset` | Three attempts, each releasing bit 7, a `tResetPause` apart; then 16#8111 | none |
| 9 | 0x6098 = 37 or 35 by SDO (current position, whichever the vendor page lists), `nMode` 6 | 0x000F, then 0x001F held until statusword bits 12 and 10; `bValid`; then 0x000F | none |
| 10 | `nMode` 8 at standstill | 0x6060 = 8, `bValid` only once 0x6061 = 8; 0x607A = 0x6064 from the new reference | none |
| 11 | The real homing method, 0x6099 speeds low | As in 9; the axis runs to the switch or index and stops | yes, slow |
| 12 | Unplug the EtherCAT cable while enabled, longer than `tInputsInvalid` | 16#8116; the drive stops by its own reaction to the lost bus. Plug it in, `bReset`, re-enable as in 7 | the drive's own stop |

## 6. What to record

For each drive, in the `s8h` bead or the pull request that closes it:

- drive family, firmware (0x100A) and TwinCAT version;
- the compiler result, and every fix it needed;
- per scenario: as expected, or what happened instead, with the `trace` output;
- each departure from the profile, phrased as a fact about that drive and firmware, for its
  vendor page, labelled as seen on the bench with the date.

Record the product, never the unit: no serial number (0x1018:04), no parameter export, no
limit or tuning values. The repository is public (`../CLAUDE.md`). When every scenario has
passed on one drive, `README.md`, Status, names the drive and firmware.
