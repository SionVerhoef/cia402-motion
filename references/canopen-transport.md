# CANopen: bringing a 402 node up

Only what it takes to get a CiA 402 drive on plain CANopen to Operational and running. Bit
timing, cabling, termination and the CAN physical layer are out of scope. Over EtherCAT none of
this applies: the EtherCAT state machine replaces NMT, and **ethercat-diagnostics** owns it.

## NMT: the node's own state

| NMT state | SDO | PDO | Enter with (COB-ID 0x000, 2 bytes: command, node ID) |
|---|---|---|---|
| Pre-operational | yes | **no** | `80 <node>` (also where a node lands after boot) |
| Operational | yes | yes | `01 <node>`: Start remote node |
| Stopped | no | no | `02 <node>` |
| (reset) | | | `81 <node>` reset node, `82 <node>` reset communication |

Node ID 0 addresses all nodes. After power-up a node sends its boot-up message (0x700 + node,
one byte 0x00) and waits in **Pre-operational**, where it answers SDOs and ignores every PDO.
A node that "answers SDOs fine but ignores the PDOs" has not been started: send `01 <node>`.

## Default COB-IDs

The predefined connection set adds the node ID (1–127) to a base:

| Object | COB-ID | Node 5 |
|---|---|---|
| NMT | 0x000 | — |
| SYNC | 0x080 | — |
| EMCY | 0x080 + node | 0x085 |
| TPDO1 / 2 / 3 / 4 (node → master) | 0x180 / 0x280 / 0x380 / 0x480 + node | 0x185 … |
| RPDO1 / 2 / 3 / 4 (master → node) | 0x200 / 0x300 / 0x400 / 0x500 + node | 0x205 … |
| SDO node → master | 0x580 + node | 0x585 |
| SDO master → node | 0x600 + node | 0x605 |
| Heartbeat, boot-up | 0x700 + node | 0x705 |

The node's actual COB-IDs are in its communication objects. Read them rather than assume the
defaults.

## PDO objects

| | Communication | Mapping |
|---|---|---|
| RPDO n | 0x1400 + n − 1 | 0x1600 + n − 1 |
| TPDO n | 0x1800 + n − 1 | 0x1A00 + n − 1 |

Communication object subindices: :01 COB-ID, where **bit 31 = 1 means the PDO is not valid**
(switched off) and bit 30 forbids remote requests; :02 transmission type; :03 inhibit time
(TPDO, in 100 µs); :05 event timer (TPDO, ms).

To remap, in Pre-operational:

1. Set bit 31 in the COB-ID (:01) to invalidate the PDO.
2. Write the mapping's :00 = 0.
3. Write the entries :01, :02, … as index << 16 | subindex << 8 | bit length.
4. Write :00 = the number of entries.
5. Write the COB-ID again with bit 31 clear.

`cia402.py pdo` checks the result against the mode. It takes the mapping values exactly as read
back from 0x1600:01….

## Transmission types

| Type | TPDO sends | RPDO data takes effect |
|---|---|---|
| 0 | on the next SYNC after a change | at the next SYNC |
| 1–240 | every n-th SYNC | at the next SYNC |
| 254, 255 | on change or the event timer (asynchronous) | at once, on receipt |

## CSP over CANopen

The cyclic modes need the drive locked to the master's cycle, which on CAN is SYNC:

- **A SYNC producer** at the cycle period: the master, or a node with bit 30 set in 0x1005. The
  period is 0x1006, in µs: 2000 for 2 ms.
- **Synchronous PDOs**, transmission type 1, in both directions. Then the feedback is sampled and
  the set-point applied on the SYNC beat. Event-driven (asynchronous) RPDOs make CSP jitter or
  fault.
- **0x60C2 interpolation time period** equal to the SYNC period.
- Each cycle: SYNC → the node's TPDOs → the master computes → the RPDOs, all before the next SYNC.

Then the 402 bring-up as on any bus: 0x6060 = 8 and wait for 0x6061, target = actual,
0x0006 → 0x0007 → 0x000F (`state-machine.md`, `modes.md`).

## Supervision

- **Heartbeat**: the node sends its NMT state on 0x700 + node every 0x1017 ms (0x00 boot-up,
  0x04 stopped, 0x05 operational, 0x7F pre-operational). The consumer side, 0x1016, lets a node
  watch the master. Node guarding is the older alternative.
- **What the drive does when it loses the master** is 0x6007, abort connection option code:
  0 nothing, 1 fault, 2 Disable voltage, 3 Quick stop. "Nothing" on a moving axis means it keeps
  following its last set-point.
- **EMCY** frames on 0x080 + node carry the error code: `errors.md`.

## Order of bring-up

1. Boot-up message seen (0x700 + node). The node is in Pre-operational.
2. By SDO: PDO mapping and communication objects, 0x1006 and SYNC, 0x60C2, heartbeat, 0x6007,
   0x6060.
3. NMT Start remote node: `01 <node>`. The heartbeat now reports 0x05.
4. SYNC running, PDOs flowing. The statusword arrives in TPDO1.
5. The 402 sequence.
