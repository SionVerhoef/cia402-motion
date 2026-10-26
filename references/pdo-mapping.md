# PDO mapping

What goes in the cyclic exchange decides what the master can do with the drive. A mapping
that lacks 0x6061 cannot confirm a mode switch. One that lacks 0x6064 cannot set
target = actual before enabling in CSP. Both mistakes compile, scan and reach OP.

## Check a mapping

```bash
python3 scripts/cia402.py pdo --mode csp --rx 6040 607A --tx 6041 6064
python3 scripts/cia402.py pdo --mode hm,csp --rx 0x60400010 0x60600008 0x607A0020 \
    --tx 0x60410010 0x60610008 0x60640020
```

Entries are hexadecimal, written `6040`, `0x607A:00`, or as the 32-bit mapping value read from
a mapping object (`0x60400010`: index 0x6040, subindex 0, 16 bits). Commas also separate.
`--mode` takes every mode the axis runs in, comma-separated. A finding is one of:

- **error**: the mode cannot be run like this. Exit status 1.
  - the controlword or the statusword is missing
  - the set-point of a cyclic mode or IP is missing, or in CSP the actual position 0x6064
  - 0x6060/0x6061 are missing although the axis switches modes
  - an object is in the wrong direction, or has the wrong length or subindex
- **warning**: it runs, but slowly or blind somewhere:
  - the set-point of PP, PV, PT or VL is missing, so every new one needs an SDO write
  - 0x6060 mapped without 0x6061
  - no feedback a mode normally needs
  - a touch probe armed without its status, or status without a latched value
  - an entry mapped twice
  - another axis appears through an object or two, with no controlword or statusword
    (a typo, or an axis only monitored); its other objects are not checked
- **note**: worth knowing:
  - neither 0x6060 nor 0x6061 mapped, so write the mode by SDO at start-up
  - 0x603F not mapped
  - a set-point of a mode not selected
  - manufacturer-specific objects
  - Beckhoff's MDP742 indices. A mapping of MDP742 objects alone gets this note and nothing
    else, since it is not a CiA 402 mapping.

The tool knows the profile, not the drive. Whether *this* drive lets you map an object, how many
entries a PDO takes, and which predefined sets it offers are device facts: ask **ethercat-esi**,
or read the ESI/EDS file. Why a drive *rejects* a mapping (an SDO abort, AL status 0x001D,
0x001E or 0x0024) is for **ethercat-diagnostics**.

## The minimum per mode

Always the controlword 0x6040 in the RxPDO and the statusword 0x6041 in the TxPDO. On top,
with "(warning)" where the tool warns instead of failing:

| Mode | RxPDO (master → drive) | TxPDO (drive → master) |
|---|---|---|
| PP | 0x607A (warning) | 0x6064 (warning) |
| VL | 0x6042 (warning) | — |
| PV | 0x60FF (warning) | 0x606C (warning) |
| PT | 0x6071 (warning) | — |
| HM | — (0x6098 by SDO) | 0x6064 (warning) |
| IP | 0x60C1:01 | 0x6064 (warning) |
| CSP | 0x607A | 0x6064 |
| CSV | 0x60FF | 0x6064 (warning) |
| CST | 0x6071 | 0x6064 (warning) |
| CSTCA | 0x6071 and 0x60EA | — |
| More than one mode | + 0x6060 | + 0x6061 |

Worth adding:

- **0x6061, always.** The only proof of which mode is running.
- **0x603F.** Without it the error code needs an SDO read after every fault.
- **0x60F4** (following error) in CSP, and **0x60FD** (limit and home switches) for homing and
  triage.
- **0x60B1/0x60B2** when the master computes velocity and torque feed-forward.
- **Touch probe:** 0x60B8 in the RxPDO, 0x60B9 and the edge values 0x60BA–0x60BD you use in
  the TxPDO (`touch-probe.md`).
- **PP:** 0x6081 profile velocity when it changes per move. Otherwise write it by SDO once.

Some drives fault, or never enable, when an object their firmware expects is missing from the
RxPDO even though the mode does not need it. If a drive with a valid mapping faults right after
OP, try its default mapping before anything else.

## How mapping works

**EtherCAT (CoE).** The RxPDO assignment 0x1C12 lists the RxPDOs in use, and the TxPDO
assignment 0x1C13 the TxPDOs. Each PDO object (0x1600–0x17FF receive, 0x1A00–0x1BFF transmit)
lists its entries as 32-bit values: index << 16 | subindex << 8 | bit length. Change them in
Pre-Op only, in this order: write subindex 0 = 0, write the entries, write subindex 0 = their
count. Then do the same for the assignment. Most masters do this from the ESI and their
start-up list. A drive with **fixed** PDOs refuses the writes. There you choose among its
predefined PDOs by changing the assignment, and some drives offer one editable PDO beside the
fixed ones. The vendor pages say which: `vendors/omron.md`, `vendors/beckhoff.md`.

**CANopen.** RPDO mapping 0x1600–0x17FF, TPDO mapping 0x1A00–0x1BFF, each with a communication
object (0x1400+ and 0x1800+) holding the COB-ID and transmission type. The PDO must be marked
invalid while it is remapped: `canopen-transport.md`.

## Multi-axis devices

Axis n uses 0x6000–0x67FF shifted by (n − 1) × 0x800: axis 2 is 0x6840 / 0x6841 / 0x687A /
0x6864. `cia402.py pdo` groups the entries by axis and checks each one apart, so a missing
0x6841 is reported against axis 2. The JSON output carries the axis of each finding.

## Beckhoff MDP742

An EL72x1 servo terminal in its default profile has no 0x6040/0x6041. Its controlword is
0x7010:01 and its statusword 0x6010:01, from Beckhoff's own MDP742 drive profile. The mapping
is not broken: it belongs to a different profile. When `cia402.py pdo` sees 0x7010 or 0x6010 it
names MDP742. A mapping of those alone it leaves at that, since it checks CiA 402 mappings only.
Mixed with CiA 402 objects, the rest is checked as usual. `vendors/beckhoff.md` explains the two
variants and how to switch.
