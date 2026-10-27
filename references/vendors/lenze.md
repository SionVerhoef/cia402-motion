# Lenze

**Read 2026-10-26**:

- **[AKB-SOD]** Lenze knowledge base 202600119, "CiA402: State machine is stuck in 'switch on
  disabled'" (last updated 2026-08-18, machine-translated), https://www.lenze.com/en-de/go/akb/202600119/1
- **[i950-TC]** Lenze knowledge base 202500375, https://www.lenze.com/en-us/go/akb/202500375/1,
  and the guide attached to it: "Commissioning example i750 and i950 with TwinCAT3" V1.1
  (2025-12-18), §2, §2.3, §4, §5, §8.2
- **[i950-CS]** Lenze knowledge base 202500394, https://www.lenze.com/en-de/go/akb/202500394/1,
  and its guide "Commissioning example i750 and i950 with Codesys V3" V1.0 (2025-12-15),
  https://download.lenze.com/AKB/English/202500394/Commissioning_example_i750_and_i950_with_Codesys_V3_V10_EN.pdf

## i550 motec and i650 motec: stuck in Switch on disabled

[AKB-SOD] The fieldbus part of these drives (iSM) can stay in **Switch on disabled** when it
should go on to Ready to switch on. The conditions:

- CiA 402 operation with velocity mode (0x6060 = 2)
- a controlword that stays unchanged
- then either a fault, or the mains supply switched off and on **while the 24 V control supply
  stays on**

The i550 cabinet and protec do not have the problem. TwinCAT NC waits for Ready to switch on,
never sends the transition again, and hangs. No root cause is given. **Fixed in firmware
version 4.7.0.13.** Before that firmware, Lenze's workaround is to trigger the transition by hand or
from PLC code. One way, our own example: write 0x0000 for a cycle, then 0x0006 again.

## i750 and i950 as CiA 402 drives

From the two commissioning guides [i950-TC, i950-CS] (firmware 1.13.0.3463 in the example):

- **Select the CiA 402 technology application first** (0x4000 = 0).
- Modes in the examples: CSP (with velocity offset, torque offset optional), CST (with velocity
  offset), CSV and velocity mode. PDO mapping is free. Both examples home in the controller, not
  with drive mode 6.
- **The default PDO set includes the velocity offset 0x60B1 and the torque limits 0x60E0/0x60E1,
  plus the Lenze words 0x2830, 0x2831 and 0x2833.** In CSP the drive needs the master's velocity
  in 0x60B1. In TwinCAT it must be linked to the NC axis by hand (the NC side is for
  **twincat-motion**). **0x60E0/0x60E1 must be written by the master** (in 0.1 %: 2000 = 200.0 %),
  or taken out of the mapping. Mapped and left at 0, they allow no torque.
- **With a motor brake, set 0x2820:1 = 0** (the brake follows the device state machine). Brake
  control through the controlword is not supported with a Beckhoff controller.
- **EtherCAT supervision**: losing Sync0 in DC mode drops the drive to Safe-Op with a fixed
  error. Missed PDO frames add 3 to a counter and good ones subtract 1. Reaching the threshold
  0x10F1:2 (Lenze recommends more than 5) raises error 0x8700. A bus disconnection raises 0x8181.
  One missed cycle is bridged by extrapolation, two in a row are not. Network-side diagnosis is
  for **ethercat-diagnostics**.
