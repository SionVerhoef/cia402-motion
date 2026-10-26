# Changelog

## Unreleased

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
