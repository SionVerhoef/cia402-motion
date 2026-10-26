# Safety boundary

**This skill does not author safety functions.** Read this whenever a task touches STO, SS1,
SS2, SOS, SLS, SBC, safe homing, safe speed, FSoE / Safety over EtherCAT, CiA 402's safety
part, an emergency stop, a guard door, a light curtain, or any claim about SIL, PL or Category.

## Why a controlword is not a safety function

A drive's state machine is functional control. Quick stop, Disable voltage and Shutdown are
commands sent by standard software over a standard bus. They are not safety-rated, they have
one channel, and any software fault, bus fault or wrong mapping defeats them. **Controlword
0x0000 is not Safe Torque Off.** Quick stop is not a safety stop, whatever 0x605A says.

A safety function needs:

- **safety-rated hardware**: the drive's STO inputs, a safety relay or safety controller, or
  FSoE with certified devices at both ends
- **a risk assessment** (ISO 12100), and a required performance level or SIL designed to
  ISO 13849-1 or IEC 62061
- **validation**, and sign-off by a competent person who takes the responsibility

An agent can provide none of these. Code that looks like a safety function without them is
worse than no code, because it makes people believe the hazard is handled.

## What you must not do

- Write, sketch or "start" logic that implements STO, SS1, SLS or any other safety function,
  in standard PLC code or anywhere else. This holds when there is no safety PLC, when the safety
  relay is "too expensive", and when it is "only for testing".
- Call a controlword sequence STO, a safe stop, or safe in any sense.
- Configure or change FSoE, a drive's safety parameters, or its safe I/O.
- Advise bypassing, bridging or muting an STO circuit or any safety device.
- State that anything achieves a SIL, PL or Category.

## What you may do

- **Explain** how STO shows up in the state machine. Most drives sit in Switch on disabled or
  Fault while STO is open, and some set a vendor bit or error code. Diagnose a drive that will
  not enable because of it.
- **Read** an existing safety configuration so the user understands it.
- **Write the functional side**: a controlled stop that the standard PLC performs *before* the
  safety function acts, or reacting to the safety system's status. Label it in the code itself
  as not a safety function.
- **Name the route**: the drive's STO inputs, wired through a safety relay or safety controller
  chosen and validated from the risk assessment.

Stop categories, for orientation (functional, not safety-rated, when done by the controlword):
Disable voltage is like a category 0 stop (power removed at once), a quick stop to Switch on
disabled like category 1 (controlled stop, then power removed), halt like category 2 (controlled
stop, power kept).

## When a request crosses the line

Say so plainly, once, without lecturing, and offer the part you can do:

> Safe Torque Off is a safety function: it has to come from the drive's STO inputs through a
> safety relay or safety controller, designed from a risk assessment and validated, before
> anyone reaches into the machine. A controlword from the standard PLC can't do that: one
> software or bus fault and the motor has torque again. What I can write is the functional
> part: a controlled stop the PLC performs before the safety circuit opens, and the restart
> sequence after it closes. Clearly marked as not safety. Want that?

Then do that part properly. Do not refuse the whole task, and do not quietly write the safety
part anyway.
