# Changelog

## Unreleased

- `SKILL.md` body: the rules, the tool, a routing table and the hand-offs to the sibling skills.
  `decode` is down to one line. Without the skill, current models decode correctly; they go
  wrong on ordering in code and on vendor facts.
- `references/`: state machine, modes, homing, objects, PDO mapping, units, touch probe,
  errors, CANopen bring-up, commissioning triage, safety boundary, and `vendors/` (deviations
  only, each with vendor, source and date).
- `scripts/cia402.py pdo`: checks a PDO mapping against the modes of an axis, per axis on a
  multi-axis device. Exit 1 on an error.
- `scripts/cia402.py`: mode 11 (cyclic synchronous torque with commutation angle) and its
  0x6502 bit 10, from Beckhoff and TI documentation. The 0x000F note now says it is the
  profile's Switch on + Enable operation command.

- `evals/`: a runner for isolated headless eval cells, the 14-task scouting set, and the
  no-skill baseline on Opus 5.5, Haiku 5.5 and Haiku 4.5 (`evals/results-scouting.md`).
- `scripts/cia402.py decode`: statusword, controlword, 0x6502, 0x6060/0x6061 and 0x6098.
  Per-state masks, a fault-first reading of non-standard statuswords, mode-specific bits and
  the homing phase.
- `scripts/cia402.py plan`: controlword sequence to any state that can be commanded, with
  transition numbers, an edge-triggered fault reset, the set-point made safe before the
  0x6061-confirmed mode switch, a quick stop left to finish before anything else, and never
  a detour through Operation enabled.
- Tests: every plan replayed on an independent model drive; statusword states, homing
  phases, commanded transitions, mode codes and homing-method directions cross-checked
  against python-canopen.
- README notices (non-affiliation, safety), `ATTRIBUTIONS.md`, CI on Linux and Windows.
- Repository scaffold: draft SKILL.md, contributor rules, CI frontmatter check.
