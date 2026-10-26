# Attributions

What this skill was built from, and what each source gave it.

## Bundled third-party content: none

Every file here is original prose, code or tables written for this skill. No third-party file
is redistributed, so no third-party notice is required. If that changes, the upstream
`LICENSE` goes next to the files and a row goes here, in the same commit. `CLAUDE.md` says
which licences may ship at all.

## Standards and specifications

| Source | What it contributed |
|---|---|
| CiA 402 / IEC 61800-7-201 (drive profile) | **Not read for this skill.** The current CiA 402 parts are open to CiA members only ([CiA technical documents](https://www.can-cia.org/cia-groups/technical-documents)), and the [IEC webstore terms](https://webstore.iec.ch/en/terms-conditions) bar using IEC publications in AI tools without IEC's permission. Object indices, bit numbers and code values are stated as facts, as public vendor manuals and permissive implementations restate them. No text, tables or figures from either document are reproduced. |

## Code and documentation consulted

| Source | Licence | How it was used |
|---|---|---|
| [python-canopen](https://github.com/canopen-python/canopen) (`canopen.profiles.p402`) | MIT | Test oracle only. `tests/test_canopen_oracle.py` imports it when installed, and CI checks the state of every statusword, the homing phases, the commanded transitions, the mode codes with their 0x6502 bits, and the homing-method directions against it. Not bundled. |
| maxon EPOS4 Firmware Specification | All rights reserved | Read. The meaning of the mode-specific controlword and statusword bits is restated as facts; EPOS4's own behaviour (bit 9, 0x000F from Ready to switch on) is named as EPOS4's. |
| [ICube Robotics `ethercat_driver_ros2`](https://github.com/ICube-Robotics/ethercat_driver_ros2) issue tracker | — | Field cases. Real statuswords from its logs are test values, among them the non-standard 0x0068 an EL7221 reported. |
| [KickCAT](https://github.com/leducp/KickCAT) | CeCILL-C (read only) | Field practice for the fault reset: a real 0 → 1 edge on bit 7, and a pause before the next command. Restated; no code copied. |

The decoder's tables started from the maintainer's own earlier statusword decoder.

## Trademarks

CiA® and CANopen® are registered EU trademarks of CAN in Automation e.V. EtherCAT® is a
registered trademark and patented technology, licensed by Beckhoff Automation GmbH, Germany.
TwinCAT® and Beckhoff® are registered trademarks of and licensed by Beckhoff Automation GmbH.
IEC is a trademark of the International Electrotechnical Commission. Other product and
company names, such as maxon and EPOS4, are trademarks of their owners.

All are used nominatively — to identify the technology this skill works with. None of these
organisations is affiliated with this project or endorses it. This project claims no
conformance to any of their specifications and uses none of their logos.
