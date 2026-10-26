# Attributions

What this skill was built from, and what each source gave it.

## Bundled third-party content: none

Every file here is original prose, code or tables written for this skill. No third-party file
is redistributed, so no third-party notice is required. If that changes, the upstream
`LICENSE` goes next to the files and a row goes here, in the same commit. `CLAUDE.md` says
which licences may ship at all.

## Code and documentation consulted

The CiA 402 / IEC 61800-7-201 documents themselves were not used. The profile's object
indices, bit numbers and code values are stated as facts, as the sources below restate them.


| Source | Licence | How it was used |
|---|---|---|
| [python-canopen](https://github.com/canopen-python/canopen) (`canopen.profiles.p402`) | MIT | Test oracle only. `tests/test_canopen_oracle.py` imports it when installed, and CI checks the state of every statusword, the homing phases, the commanded transitions, the mode codes with their 0x6502 bits, and the homing-method directions against it. Not bundled. |
| maxon EPOS4 Firmware Specification (edition 2026-07) | All rights reserved | Read. The meaning of the mode-specific controlword and statusword bits is restated as facts; EPOS4's own behaviour is on `references/vendors/maxon.md`, named as EPOS4's. |
| Beckhoff Information System, EL72x1-901x and EL72x1-001x documentation | All rights reserved | Read. MDP742 vs DS402, the DS402 objects, PDO sets and mode 11, restated on `references/vendors/beckhoff.md`. |
| Omron 1S-series User's Manual I586-E1-19 | All rights reserved | Read. PDO and gear facts on `references/vendors/omron.md`. |
| Synapticon SOMANET Object Dictionary 5.4 and online documentation | All rights reserved | Read. Option codes, homing and PP facts on `references/vendors/synapticon.md`. |
| Nanotec CL3-E and NP5-20 technical manuals | All rights reserved | Read. Option codes, PP and homing facts on `references/vendors/nanotec.md`. |
| LinMot EtherCAT CiA402 Profile Interface (0185-1178-E_1V0) | All rights reserved | Read. Deviations on `references/vendors/linmot.md`. |
| Texas Instruments Industrial Communications SDK, EtherCAT SubDevice CiA402 example | All rights reserved | Read. Lists mode 11 among the modes drives are recommended to support. |
| Lenze knowledge base 202600119, 202500375, 202500394 and their commissioning guides | All rights reserved | Read. Facts on `references/vendors/lenze.md`. |
| HIWIN Drive User Guide v1.0 (2014) | All rights reserved | Read. Homing facts on `references/vendors/hiwin.md`. |
| CODESYS SoftMotion, Generic CiA402 Axis configuration page | All rights reserved | Read. Its compatibility parameters are named on `references/vendors/README.md`. |
| [ICube Robotics `ethercat_driver_ros2`](https://github.com/ICube-Robotics/ethercat_driver_ros2) issue tracker | — | Field cases. Real statuswords from its logs are test values, among them the non-standard 0x0068 an EL7221 reported. |
| [KickCAT](https://github.com/leducp/KickCAT) | CeCILL-C (read only) | Field practice for the fault reset: a real 0 → 1 edge on bit 7, and a pause before the next command. Restated; no code copied. |

The decoder's tables started from the maintainer's own earlier statusword decoder.

## Trademarks

CiA® and CANopen® are registered EU trademarks of CAN in Automation e.V. EtherCAT® is a
registered trademark and patented technology, licensed by Beckhoff Automation GmbH, Germany.
TwinCAT® and Beckhoff® are registered trademarks of and licensed by Beckhoff Automation GmbH.
IEC is a trademark of the International Electrotechnical Commission. Other product and
company names, such as maxon, EPOS4, Omron, Synapticon, SOMANET, Nanotec, LinMot, Lenze,
HIWIN, CODESYS and Texas Instruments, are trademarks of their owners.

All are used nominatively — to identify the technology this skill works with. None of these
organisations is affiliated with this project or endorses it. This project claims no
conformance to any of their specifications and uses none of their logos.
