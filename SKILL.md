---
name: cia402-motion
description: "Use for the CiA 402 (IEC 61800-7) drive profile on any vendor's servo or stepper drive: the controlword/statusword state machine, why a drive is stuck in Switch On Disabled or Fault, modes of operation (CSP, CSV, CST, PP, PV, homing), CoE object dictionary entries (0x6040, 0x6041, 0x6060, 0x6061, 0x607A) and PDO mapping. Not for TwinCAT NC axis configuration or MC_ blocks (use twincat-motion) or EtherCAT network faults (use ethercat-diagnostics). DRAFT: under development."
---

# cia402-motion

> **Draft.** This skill is under development and not ready to install.
>
> **Reference material only. Not for safety functions.** Drive configuration must be
> reviewed and validated by a qualified engineer against the drive's own documentation.

## Goal

Bring a CiA 402 drive through its state machine into Operation Enabled in the right mode,
and diagnose why it will not get there.
