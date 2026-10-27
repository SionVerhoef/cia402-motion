# Commissioning triage

Start from the symptom, then work down the list in order. Each step rules out a layer, so a
later step's advice is wrong while an earlier one is still open.

## What to ask for first

- the drive (make, model, firmware) and the master (TwinCAT, CODESYS, ROS 2, own code), and the
  bus: EtherCAT or CANopen
- **the statuswords as logged**, over time, not one value, and the controlwords the master sent
  in the same cycles
- 0x6060 and 0x6061, 0x603F, and the PDO mapping
- what changed since it last worked

Decode with the tool, not by eye: `cia402.py decode sw <word> [--mode m]`.

## 0. Is the bus up?

- **EtherCAT**: every slave in OP and the working counter valid (WcState 0)? If not, stop here
  and hand to **ethercat-diagnostics**. A drive cannot follow a controlword that never arrives.
- **CANopen**: does the heartbeat say 0x05, Operational? Not started → `canopen-transport.md`.
- **Does the controlword arrive?** Read 0x6040 back by SDO while the master writes it. A
  mapping that is not linked in the master, or a second writer overwriting it, shows up here.

## 1. The drive will not enable

Find the state from the statusword, then:

| State | Check, in order |
|---|---|
| **Not ready to switch on** for good | The drive is still booting or self-testing, or is missing its own configuration (motor data, feedback). Not a controlword problem: look at the drive's display or tool. |
| **Switch on disabled** | 1. Is the master sending 0x0006, with bit 2 = 1 and bit 7 = 0? 0x000B, 0x0002 and anything with bit 7 set are not Shutdown. 2. Remote (bit 9) = 0: a commissioning tool or keypad may hold control. 3. STO or an enable input open: many drives sit in Switch on disabled (or Fault) until the STO circuit is closed. That is hardware, read only: `safety-boundary.md`. 4. A known firmware issue: `vendors/lenze.md`. |
| **Ready to switch on**, no further | Voltage enabled (bit 4) = 0: no DC link or mains, or an open main contactor. That holds on drives that use the profile's meaning; maxon EPOS4 sets bit 4 only once the power stage is on (`vendors/maxon.md`). Then check that 0x0007 is really sent. |
| **Switched on**, no further | Is 0x000F really sent? Is a valid mode set (0x6061 ≠ 0)? Some drives refuse to enable without one. Is a brake or enable condition of the drive's own missing? 0x603F after the attempt. |
| **Fault** | Read 0x603F *before* anything else. Then: the reset is an edge (0x0000 → 0x0080 → 0x0000), followed by 0x0006 → 0x0007 → 0x000F. A level 0x0080, 0x008F or 0x000F straight from Switch on disabled are the usual code bugs: `state-machine.md`. |
| **Non-standard word** (e.g. 0x0068) | Treat as Fault if bit 3 is set. The tool says which bits clash. |
| Toggles **Fault ↔ Switch on disabled** | The cause is still there, or the enable sequence itself causes it, typically target ≠ actual in CSP → following error on enable. |

## 2. It enables, then faults or trips at once

1. **CSP: target ≠ actual on enable.** The most common cause by far: `modes.md`.
2. **The mode was switched without waiting for 0x6061**: the drive was still in the old mode when
   the new set-points came.
3. **Sync errors** (EtherCAT DC, CANopen SYNC): **ethercat-diagnostics**, or `canopen-transport.md`.
4. A brake that does not release, motor phasing or commutation, current limits: the drive's own
   tool and manual.

## 3. The axis jumps

- **On enable**: target = actual was not set before T4.
- **After homing**: the reference moved, but the master kept the pre-homing target.
- **After a mode switch**: no 0x6061 check, or the new mode's set-point was not prepared.

## 4. Enabled, but it does not move

| Mode | Check |
|---|---|
| any | 0x6061 is the mode you think. Halt (bit 8) is not set. Quick stop (bit 2) is 1. Internal limit (bit 11): software limits 0x607D, limit switches 0x60FD, a torque limit 0x6072 or 0x60E0/0x60E1 of 0 |
| PP | A rising edge on bit 4 per move, with the bit-12 handshake. 0x6081 and 0x6083/0x6084 non-zero (`modes.md`) |
| PV | 0x60FF and the ramps non-zero |
| CSP/CSV/CST | Set-points are really changing every cycle. Bit 12 = 1 (the drive follows the command value) |
| HM | Bit 4 held high through the whole run. The phase from bits 13/12/10 (`homing.md`) |

## 5. It moves wrong

- **Wrong distance or speed**: master and drive disagree on user units: `units.md`.
- **Wrong direction**: polarity 0x607E set in the drive *and* the master, or in neither.
- **Homes to the wrong place**: method, switch polarity, a vendor method number carried over from
  another drive (`homing.md`), how 0x607C is applied.

## 6. It stops or disables by itself

- **A quick stop it did not ask for**: is bit 2 dropping? A master that writes 0x0000 or 0x000B for
  a cycle on reconnect or start-up does this.
- **Communication loss**: the reaction is set in 0x6007, on CANopen and on many EtherCAT drives
  (maxon EPOS4 and LinMot, for example). On EtherCAT there is also the sync-manager watchdog
  (**ethercat-diagnostics**).
- **STO opened** by the safety circuit: the drive is doing its job. Read only.
- **A fault reaction**: 0x605E and 0x603F.

## Hand-offs

| Symptom | Owner |
|---|---|
| Slaves not in OP, WcState ≠ 0, lost frames, DC/sync errors, SDO aborts, mapping rejected | **ethercat-diagnostics** |
| What this drive supports: its modes, objects, allowed values, mappable and default PDOs | **ethercat-esi** |
| TwinCAT NC: axis config, MC_ blocks, NC scaling, NC homing, MC_Power.Status FALSE while the drive is fine | **twincat-motion** (it hands back here when the drive never reaches Operation enabled) |
| Writing or reviewing the PLC code itself | **twincat-st** |
| Diagnosis from a TwinCAT Scope recording | **twincat-scope** |
| STO, SS1, SLS, FSoE, CiA 402 safety | nobody authors it: `safety-boundary.md` |
