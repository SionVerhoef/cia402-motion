# Errors, warnings and emergency messages

## 0x603F error code

The last error, as a 16-bit code from the CiA 301 emergency classes. The class is fixed by the
leading digits. The exact meaning, and often more detail, is the vendor's. Read the class
here, then look the full code up in the drive manual.

| Code | Class |
|---|---|
| 0x0000 | no error (or the error was reset) |
| 0x1000 | generic |
| 0x2xxx | current: 0x21xx input side, 0x22xx inside the device, 0x23xx output side (0x2310: continuous overcurrent) |
| 0x3xxx | voltage: 0x31xx mains, 0x32xx inside the device (0x3210 DC-link overvoltage, 0x3220 undervoltage), 0x33xx output |
| 0x4xxx | temperature: 0x41xx ambient, 0x42xx device (0x4210: excess temperature) |
| 0x5xxx | device hardware |
| 0x6xxx | device software: 0x61xx internal, 0x62xx user software, 0x63xx data set |
| 0x7xxx | additional modules (encoders and sensors often sit here) |
| 0x8xxx | monitoring: 0x81xx communication (0x8130 heartbeat or life guard lost), 0x82xx protocol (0x8210 PDO length), 0x86xx position control (0x8611 following error) |
| 0x9xxx | external error |
| 0xFFxx | device-specific |

A drive in Fault with 0x603F = 0 is not fault-free. Read the vendor's diagnostic objects (on
EtherCAT often the diagnosis history 0x10F3) or the error history 0x1003. Some drives clear
0x603F on the reset, so log it before resetting.

## Warning (statusword bit 7)

The drive keeps running and reports a condition that may become a fault: temperature rising,
I²t approaching a limit, a following error inside a warning band. There is no warning code
object in the profile. The detail is in the drive's own objects.

## Emergency messages (EMCY)

When an error occurs the drive sends an emergency message: the 16-bit error code, the error
register 0x1001, and five manufacturer bytes.

- **CANopen**: a frame on COB-ID 0x080 + node ID (node 5: 0x085), 8 data bytes. 0x1014 holds the
  COB-ID and 0x1015 the inhibit time.
- **EtherCAT**: the same content as a CoE emergency in the mailbox. A master sees it only if it
  reads the mailbox. How a particular master shows them, and EtherCAT's own diagnostics, belong
  to **ethercat-diagnostics**.

Error register 0x1001: bit 0 generic, 1 current, 2 voltage, 3 temperature, 4 communication,
5 device-profile-specific, 7 manufacturer-specific.

## Following error

In PP and CSP the drive raises statusword bit 13 when the position deviation exceeds the
following-error window 0x6065 for longer than 0x6066. It typically faults with 0x8611. 0x60F4 is
the deviation itself. A following error **at the moment of enabling** is almost never tuning.
It is target ≠ actual in CSP, or a mode switch that was not confirmed: `modes.md`.

## From the code to the fix

1. Decode the statusword (`cia402.py decode sw`): Fault, Fault reaction active, or a warning only.
2. Read 0x603F *before* resetting. Note the class.
3. Look up the full code in the drive manual. Check the drive's diagnostic history for detail.
4. Fix the cause, then reset with an edge on bit 7 (`state-machine.md`). If the same code comes
   back at once, the cause is still there. Do not loop resets.
