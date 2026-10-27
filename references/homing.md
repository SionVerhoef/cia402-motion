# Homing (mode 6)

Drive-based homing: the drive runs the search itself and sets its position reference. This
page covers the methods, the status bits and the sequence. Homing done by the master instead
(the PLC moves to a switch and sets the position, or TwinCAT NC's `MC_Home`) belongs to the
**twincat-motion** skill.

## Objects

| Object | Type | What |
|---|---|---|
| 0x6098 homing method | INT8 | which search; written before homing starts, usually by SDO |
| 0x6099:01 | UINT32 | speed while searching for the switch |
| 0x6099:02 | UINT32 | speed while searching for the zero (index pulse or switch edge) |
| 0x609A homing acceleration | UINT32 | |
| 0x607C home offset | INT32 | the offset between the found home and the position zero |

Manuals word the use of 0x607C differently: whether the offset is added or subtracted, and
whether the drive then moves to the new zero. Check the drive's manual, then home once and read
0x6064 to see what this drive does.

## Methods

`cia402.py decode method <n>` names any number.

| Methods | Search |
|---|---|
| 1, 2 | limit switch (1 negative, 2 positive), then the index pulse |
| 3–6 | home switch (3, 4 positive side; 5, 6 negative side), then the index pulse |
| 7–14 | home switch with reversal at a limit switch (7–10 positive, 11–14 negative), then the index pulse |
| 17–30 | the same as 1–14 (method minus 16), without the index pulse |
| 33, 34 | index pulse only (33 negative, 34 positive) |
| 35, 37 | the current position becomes home; no motion |
| 15, 16, 31, 32, 36 | reserved |
| negative | **manufacturer-specific** |

Neighbouring numbers differ in which edge of the switch counts and from which side it is
approached. Check the method diagram in the drive manual against the real switch, wired
polarity included. 35 and 37 mean the same, but drives differ in which they accept: maxon EPOS4
takes only 37, Nanotec's CL3-E documents only 35, and Synapticon takes both (vendor pages). Many
drives support only some of the standard methods.

**No standard method homes on a hard stop.** Homing against a mechanical end stop (by current
threshold or following error) is always a vendor method with a negative number, or it is done
by the master.

## Negative methods are not portable

The same negative number means different things on different drives, sometimes with the
direction reversed. As read 2026-10-26:

| Source | −1 | −2 | −3 | −4 | Other negatives |
|---|---|---|---|---|---|
| maxon EPOS4 (`vendors/maxon.md`) | hard stop **positive** + index | hard stop negative + index | hard stop positive | hard stop negative | none |
| Synapticon SOMANET v5 (`vendors/synapticon.md`) | end stop **negative** + index | end stop positive + index | end stop negative | end stop positive | none |
| Nanotec (`vendors/nanotec.md`) | block, negative + index | block, positive + index | — | — | −7 to −14, −17, −18, −23 to −30: block versions of the positive methods |
| LinMot (`vendors/linmot.md`) | — | — | — | — | only −128 to −111, its own list |
| python-canopen 2.4.1 names (a library, not a drive) | mechanical limit negative + index | mechanical limit positive + index | negative | positive | −5 to −8: following error |

**Never carry a negative method number from one drive to another.** Look up what the old
number did (search, direction, index or not), then find the new drive's method that does the
same. It may have a different number, or not exist; then use a home switch, an index method, or
master-side homing. Do not substitute a positive method as if it were equivalent. The vendor
pages list what each drive offers.

## Status: bits 13, 12 and 10

Only meaningful in Operation enabled with 0x6061 = 6. `cia402.py decode sw <word> --mode hm`
gives the phase.

| Bits 13 12 10 | Mask 0x3400 | Phase |
|---|---|---|
| 0 0 0 | 0x0000 | in progress |
| 0 0 1 | 0x0400 | interrupted, or not started |
| 0 1 0 | 0x1000 | attained, target not reached yet |
| 0 1 1 | 0x1400 | **completed** |
| 1 0 0 | 0x2000 | error, motor still moving |
| 1 0 1 | 0x2400 | error, at standstill |

Bit 13 in homing is **homing error**, not following error. Done means bits 12 and 10 are both
set; bit 12 alone means the reference is found but the axis is still moving to the zero. Not
every drive follows this table exactly. CODESYS's generic CiA 402 axis carries several
compatibility switches for drives that set these bits in their own order (`vendors/README.md`).

## Sequence

1. With the drive enabled or not, write 0x6060 = 6 and wait for 0x6061 = 6.
2. Write 0x6098 and the speeds and acceleration (by SDO, before starting).
3. In Operation enabled: raise controlword bit 4 and **keep it high** until homing ends.
   Dropping it interrupts the run (status 0x0400).
4. Wait, with an overall timeout, for completed (0x1400). Fail at once on bit 13.
5. Clear bit 4.
6. Before the next mode: target = actual (0x607A = 0x6064), then switch the mode with the 0x6061
   check (`modes.md`). Homing has just moved the reference, so a target computed before homing is
   wrong now.

After an error: read 0x603F and the drive's diagnostics. Check the switch wiring and polarity,
the method, the speeds and the limits, then start again with a new rising edge on bit 4.

Whether the drive still counts as homed after a power cycle depends on the encoder (absolute or
not) and the vendor. Do not keep a "homed" flag in the master through a restart unless the
drive confirms it.
