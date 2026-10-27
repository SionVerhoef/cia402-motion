# Omron 1S servo drives (R88D-1SN…-ECT)

**Read 2026-10-26**: Omron 1S-series AC Servo System with built-in EtherCAT, User's Manual
I586-E1-19, https://files.omron.eu/downloads/latest/manual/en/i586_1s_series_users_manual_en.pdf.
Sections are given in brackets.

Two claims circulate, and models answering without this skill repeat them: that the 1S has only
fixed PDOs, and that it has no 0x6091 and keeps its gear in a vendor object. Both are wrong.

## PDOs: fixed sets plus one editable pair

From sections 5-4-3 and 5-4-4:

- **The fixed mappings 0x1701–0x1705 (RxPDO) and 0x1B01–0x1B04 (TxPDO) cannot be edited.** You
  choose among them in the assignment objects 0x1C12/0x1C13.
- **One editable pair: RxPDO 0x1600 and TxPDO 0x1A00.** To add an object that no fixed set has
  (the velocity offset 0x60B1, say), assign 0x1600 via 0x1C12 and map it there. Edits are
  accepted in Pre-Op only and are not kept through
  power-off, so the master must write them at every start-up. At most 6 entries at a 125 µs
  cycle, 10 otherwise.

## Gear: 0x6091 exists, 0x6092 does not

From sections 7-7, 9-2 and App. A-2-8, read together:

- **The electronic gear is 0x6091:01 (motor revolutions) and 0x6091:02 (shaft revolutions).**
  0x3001:05/:06 mirror it. **0x6092 (feed constant) is absent.**
- **The gear works only at cycle times of 250 µs or more.** At 125 µs it must be 1:1.
- **With an Omron NJ/NX controller the gear stays 1:1**, and the controller does the scaling.
