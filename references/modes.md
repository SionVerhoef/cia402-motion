# Modes of operation

The master asks for a mode in 0x6060 (INT8) and the drive reports the one it is actually in
on 0x6061. The mode decides what the set-point objects mean and what controlword bits 4–6 and
9 and statusword bits 10, 12 and 13 do.

## Codes

| Code | Mode | 0x6502 bit | Set-point | Who makes the trajectory |
|---|---|---|---|---|
| 1 | PP, profile position | 0 | 0x607A target position | drive |
| 2 | VL, velocity | 1 | 0x6042 vl target velocity | drive |
| 3 | PV, profile velocity | 2 | 0x60FF target velocity | drive |
| 4 | PT, profile torque | 3 | 0x6071 target torque | drive |
| 6 | HM, homing | 5 | method in 0x6098 | drive |
| 7 | IP, interpolated position | 6 | 0x60C1 interpolation data | master, drive interpolates |
| 8 | CSP, cyclic synchronous position | 7 | 0x607A, every cycle | master |
| 9 | CSV, cyclic synchronous velocity | 8 | 0x60FF, every cycle | master |
| 10 | CST, cyclic synchronous torque | 9 | 0x6071, every cycle | master |
| 11 | CSTCA, CST with commutation angle | 10 | 0x6071 and 0x60EA, every cycle | master |

0 means no mode. Negative codes are manufacturer-specific, and the same number means
different things on different drives. 0x6502 bits 16–31 are the vendor's own modes.

Mode 11 is in few drives. Beckhoff documents it for the EL72x1 in DS402: target torque 0x6071
plus the commutation angle 0x60EA (`vendors/beckhoff.md`). TI's Industrial Communications SDK
lists it among the modes drives are recommended to support ("EtherCAT SubDevice: CiA402
Example", section Operation modes, read 2026-10-26,
https://software-dl.ti.com/processor-industrial-sw/esd/ind_comms_sdk/am243x/2026_00_00_06/docs/am243x/ethercat_subdevice/example2.html).
python-canopen stops at 10.

`cia402.py decode modes <0x6502>` lists what a drive claims; `decode mode <n>` names one code.
What a *particular* drive supports is a device fact. Read its 0x6502, or ask the
**ethercat-esi** skill (or the drive's ESI/EDS file) rather than assuming a mode exists.

## Switching modes

1. Make the set-point of the **new** mode safe: in CSP target = actual, in velocity and torque
   modes a zero set-point, in PP bit 4 low.
2. Write 0x6060.
3. **Wait until 0x6061 reads the new code**, with a timeout. Until it does, the mode-specific
   bits and set-points still mean what they meant in the old mode.
4. Only then use the new mode's bits and set-points.

Map 0x6061 into the TxPDO, or poll it. A fixed delay instead of the 0x6061 check works on the
bench and fails intermittently on the machine. The profile allows a switch while enabled.
Whether the drive follows the new set-point the instant 0x6061 changes, or needs to be
disabled to switch, is vendor-specific. Plan for the first. After drive-based homing, homing
has just moved the position reference, so the new mode starts from 0x6064, never from a
position computed earlier. `cia402.py plan --mode <mode>` adds steps 1–3 on the way into
Operation enabled.

## Mode-specific bits

| Mode | CW 4 | CW 5 | CW 6 | CW 9 | SW 10 | SW 12 | SW 13 |
|---|---|---|---|---|---|---|---|
| PP | new set-point (edge) | change set immediately | relative (0 = absolute) | change on set-point | target reached | set-point acknowledge | following error |
| PV | — | — | — | — | target reached | speed is zero | max slippage error |
| PT | — | — | — | — | target reached | — | — |
| HM | homing start (edge; 1 → 0 interrupts) | — | — | — | target reached | homing attained | homing error |
| IP | enable interpolation | — | — | — | target reached | interpolation active | — |
| CSP | — | — | — | — | — | follows the command value | following error |
| CSV / CST | — | — | — | — | — | follows the command value | — |

"—" is reserved in that mode: write 0, ignore on read. Halt (CW bit 8) belongs to the profile
modes. Whether it also works in homing differs: LinMot's does not (`vendors/linmot.md`). In the
cyclic modes the master stops the axis through its set-points. CSTCA's
bits are not in the table: no source read for this skill gives them. With `--mode`,
`cia402.py decode sw|cw` applies this table.

In homing, bits 13, 12 and 10 together give the phase: `homing.md`.

## Profile position (PP): the set-point handshake

Holding 0x001F every cycle moves the axis once. After that, new targets are ignored, because
bit 4 acts on its rising edge.

1. Write the target 0x607A (and bit 6 for relative).
2. Raise bit 4.
3. Wait for statusword bit 12 (set-point acknowledge) = 1.
4. Clear bit 4.
5. Wait for bit 12 = 0: the drive can take the next set-point.

Bit 5 = 1 replaces the running move at once, bit 5 = 0 queues the new one after it. Bit 10
(target reached) goes high when the axis is inside the position window 0x6067 for 0x6068.
Profile velocity 0x6081 and acceleration/deceleration 0x6083/0x6084 must be non-zero; generic
masters often do not send them unless they are mapped or written at start-up, and some drives
then refuse to move while others use a default that may be far too fast. Clamp with 0x607F max
profile velocity.

## Profile velocity and torque (PV, PT)

PV follows 0x60FF with the ramps 0x6083/0x6084. Bit 12 says the speed is zero, and bit 10
says it is within the velocity window 0x606D for 0x606E. PT follows 0x6071 with the slope
0x6087. Torque is in thousandths of rated torque (`units.md`).

## Cyclic synchronous modes (CSP, CSV, CST)

The master generates the trajectory and sends a new set-point every cycle. The drive closes its
loops on it. Three rules matter more than any tuning.

- **Target = actual before Operation enabled.** While the drive is not enabled, copy 0x6064
  into 0x607A every cycle, enable, then start the trajectory from the actual position. With
  target ≠ actual the drive goes for the target at once: the axis jumps, or trips on following
  error. The same holds after homing and after a mode switch. A master that sends 0 because
  "nothing is commanded yet" sends the axis to 0.
- **A synchronised bus.** The set-point must arrive on a fixed period that the drive's loop is
  locked to. On EtherCAT that is distributed clocks with SYNC0; on CANopen, SYNC with synchronous
  PDOs (`canopen-transport.md`). The interpolation time period 0x60C2 (sub 1 value, sub 2 a
  power of ten in seconds, e.g. 2 and −3 for 2 ms) should equal the cycle. Sync errors
  themselves are a network problem: hand them to **ethercat-diagnostics**.
- **Bit 12 = 0 in Operation enabled means the drive is not following the set-point.** Look for
  why (a limit, a vendor condition) before blaming the trajectory.

Feed-forward goes in 0x60B1 (velocity offset) and 0x60B2 (torque offset); 0x60B0 offsets the
position. In CSP, following error (bit 13) is raised when the deviation exceeds 0x6065 for
longer than 0x6066; 0x60F4 is the deviation itself.

## Interpolated position and velocity mode (IP, VL)

IP predates CSP and is rare on EtherCAT drives. The master sends interpolation points in 0x60C1
with bit 4 enabling interpolation, and the drive interpolates between them at 0x60C2. VL is the
frequency-inverter mode, with its own 16-bit objects 0x6042–0x6044. `cia402.py` does not decode
VL's ramp bits.
