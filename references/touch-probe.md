# Touch probe

A touch probe latches the position on an edge of a fast input or of the encoder's index pulse,
in the drive, without bus delay. It is used for registration marks, measuring, and homing done
by the master. Two probes are defined. Probe 1 uses the low byte of each word, probe 2 the high
byte. Master-side function blocks (TwinCAT `MC_TouchProbe`) belong to **twincat-motion**.

## 0x60B8 touch probe function (master → drive)

| Bit (probe 1) | Bit (probe 2) | Meaning |
|---|---|---|
| 0 | 8 | enable the probe |
| 1 | 9 | 0 = latch the first event only, 1 = latch continuously |
| 2–3 | 10–11 | trigger: 00 the probe input, 01 the encoder zero pulse, 10 the source in 0x60D0, 11 reserved |
| 4 | 12 | latch on the rising edge |
| 5 | 13 | latch on the falling edge |
| 6–7 | 14–15 | reserved or vendor-defined |

## 0x60B9 touch probe status (drive → master)

| Bit (probe 1) | Bit (probe 2) | Meaning |
|---|---|---|
| 0 | 8 | probe enabled |
| 1 | 9 | a rising-edge position is stored |
| 2 | 10 | a falling-edge position is stored |
| 6–7 | 14–15 | vendor-defined (some drives toggle one in continuous mode, so a new latch can be seen) |

Latched positions: 0x60BA probe 1 rising, 0x60BB probe 1 falling, 0x60BC probe 2 rising,
0x60BD probe 2 falling. 0x60D0:01/:02 selects the source when bits 2–3 are 10. Its values
beyond the probe inputs are vendor-defined.

## Using it

1. Map 0x60B8 into the RxPDO, and 0x60B9 plus the edge value you need into the TxPDO.
   `cia402.py pdo` warns when 0x60B8 is mapped without 0x60B9, and when 0x60B9 is mapped
   without any edge value.
2. Arm: enable bit plus the edge bit, e.g. 0x0011 for probe 1 on its input, rising edge, first
   event only.
3. Wait for the stored bit in 0x60B9, then read the position.
4. **To latch again in first-event mode, re-arm.** The drive latches once per arming. Drives
   differ in which bit must make the 0 → 1 edge, so clear the enable and edge bits together and
   set them again.
5. In continuous mode the value is overwritten on every edge. Tell a new value from an old one by
   the vendor's toggle bit, or by comparing values.

Latch positions are in the same user units as 0x6064. Check which encoder a probe latches on a
drive with two (motor and load), and whether the input needs a minimum pulse width. Both are in
the drive manual.
