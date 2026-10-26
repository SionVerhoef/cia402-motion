# Objects

The profile objects a commissioning engineer meets, grouped by job. Types are the profile's.
"PDO" marks the ones normally mapped into the cyclic exchange; the others are written once
by SDO. A drive may leave any of them out or add restrictions. Ask **ethercat-esi**, or read
the drive's ESI/EDS file, for what a particular drive has, its value ranges and what it lets you
map.

0x2000–0x5FFF is the manufacturer's range. Its meaning is in the drive manual and never
carries over between vendors.

## Device control

| Index | Name | Type | | Notes |
|---|---|---|---|---|
| 0x603F | Error code | UINT16 | PDO | last error, CiA 301 classes: `errors.md` |
| 0x6040 | Controlword | UINT16 | PDO | `state-machine.md` |
| 0x6041 | Statusword | UINT16 | PDO | |
| 0x605A | Quick stop option code | INT16 | | how T11 stops; decides whether T16 exists |
| 0x605B | Shutdown option code | INT16 | | how T8 stops |
| 0x605C | Disable operation option code | INT16 | | how T5 stops |
| 0x605D | Halt option code | INT16 | | how halt (bit 8) stops |
| 0x605E | Fault reaction option code | INT16 | | how the drive stops on a fault |
| 0x6007 | Abort connection option code | INT16 | | reaction to losing the master: 0 none, 1 fault, 2 Disable voltage, 3 Quick stop |
| 0x6060 | Modes of operation | INT8 | PDO | requested mode: `modes.md` |
| 0x6061 | Modes of operation display | INT8 | PDO | the mode actually running |
| 0x6502 | Supported drive modes | UINT32 | | bit (code − 1) per mode |

## Position

| Index | Name | Type | | Notes |
|---|---|---|---|---|
| 0x607A | Target position | INT32 | PDO | PP and CSP set-point |
| 0x6062 | Position demand value | INT32 | PDO | the drive's own set-point after its profile |
| 0x6063 | Position actual internal value | INT32 | PDO | in encoder increments |
| 0x6064 | Position actual value | INT32 | PDO | in user units: `units.md` |
| 0x6065 | Following error window | UINT32 | | following error when exceeded… |
| 0x6066 | Following error time out | UINT16 | | …for longer than this (ms) |
| 0x6067 | Position window | UINT32 | | target reached when inside… |
| 0x6068 | Position window time | UINT16 | | …for this long (ms) |
| 0x607B | Position range limit | INT32 ×2 | | wrap-around range (modulo) |
| 0x607D | Software position limit | INT32 ×2 | | :01 min, :02 max |
| 0x607E | Polarity | UINT8 | | bit 7 reverses position, bit 6 velocity |
| 0x60B0 | Position offset | INT32 | PDO | added to the CSP set-point |
| 0x60F4 | Following error actual value | INT32 | PDO | |

## Velocity

| Index | Name | Type | | Notes |
|---|---|---|---|---|
| 0x60FF | Target velocity | INT32 | PDO | PV and CSV set-point |
| 0x606B | Velocity demand value | INT32 | PDO | |
| 0x606C | Velocity actual value | INT32 | PDO | |
| 0x606D / 0x606E | Velocity window / time | UINT16 | | PV target reached |
| 0x606F / 0x6070 | Velocity threshold / time | UINT16 | | PV speed-is-zero bit |
| 0x607F | Max profile velocity | UINT32 | | clamp on profile moves |
| 0x6080 | Max motor speed | UINT32 | | |
| 0x6081 | Profile velocity | UINT32 | | PP move speed |
| 0x60B1 | Velocity offset | INT32 | PDO | velocity feed-forward in CSP |

## Torque and current

Torque and current are in thousandths of the rated value (0x6076, 0x6075).

| Index | Name | Type | | Notes |
|---|---|---|---|---|
| 0x6071 | Target torque | INT16 | PDO | PT, CST set-point |
| 0x6072 | Max torque | UINT16 | PDO | |
| 0x6073 | Max current | UINT16 | | |
| 0x6074 | Torque demand | INT16 | PDO | |
| 0x6075 | Motor rated current | UINT32 | | mA |
| 0x6076 | Motor rated torque | UINT32 | | mN·m |
| 0x6077 | Torque actual value | INT16 | PDO | |
| 0x6078 | Current actual value | INT16 | PDO | |
| 0x6087 | Torque slope | UINT32 | | PT ramp |
| 0x60B2 | Torque offset | INT16 | PDO | torque feed-forward |
| 0x60E0 / 0x60E1 | Positive / negative torque limit value | UINT16 | PDO | |

## Profiles and ramps

| Index | Name | Type | Notes |
|---|---|---|---|
| 0x6083 | Profile acceleration | UINT32 | PP, PV |
| 0x6084 | Profile deceleration | UINT32 | also the slow-down ramp of the option codes |
| 0x6085 | Quick stop deceleration | UINT32 | the quick-stop ramp |
| 0x6086 | Motion profile type | INT16 | 0 linear (trapezoid); others vendor-dependent |

## Homing, touch probe, interpolation, I/O

| Index | Name | Type | | Page |
|---|---|---|---|---|
| 0x6098 | Homing method | INT8 | | `homing.md` |
| 0x6099 | Homing speeds | UINT32 ×2 | | |
| 0x609A | Homing acceleration | UINT32 | | |
| 0x607C | Home offset | INT32 | | |
| 0x60B8 | Touch probe function | UINT16 | PDO | `touch-probe.md` |
| 0x60B9 | Touch probe status | UINT16 | PDO | |
| 0x60BA–0x60BD | Touch probe 1/2 positive/negative edge | INT32 | PDO | |
| 0x60D0 | Touch probe source | INT16 ×2 | | |
| 0x60C1 | Interpolation data record | INT32 | PDO (:01) | IP set-point |
| 0x60C2 | Interpolation time period | UINT8 + INT8 | | cycle = value × 10^index s |
| 0x60FD | Digital inputs | UINT32 | PDO | bit 0 negative limit, 1 positive limit, 2 home switch |
| 0x60FE | Digital outputs | UINT32 ×2 | PDO (:01) | :01 outputs (bit 0 brake), :02 mask |

## Units

| Index | Name | Type | Page |
|---|---|---|---|
| 0x608F | Position encoder resolution | UINT32 ×2 | `units.md` |
| 0x6091 | Gear ratio | UINT32 ×2 | |
| 0x6092 | Feed constant | UINT32 ×2 | |
| 0x6096 | Velocity factor | UINT32 ×2 | |
| 0x60A8 / 0x60A9 | SI unit position / velocity | UINT32 | |

## More than one axis in one device

A multi-axis device repeats the 0x6000–0x67FF block once per axis, 0x800 apart: axis 2's
controlword is 0x6840, its statusword 0x6841, axis 3's controlword 0x7040. `cia402.py pdo`
recognises the offset and checks each axis on its own. Not every multi-axis product follows
this: some appear as separate slaves or nodes, one per axis, each with its own 0x6040. On
EtherCAT the device's ESI says how many CiA 402 axes it has. Ask **ethercat-esi**.
