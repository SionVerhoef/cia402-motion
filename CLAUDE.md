# Working on this repository

These rules apply to anyone — human or agent — **editing this repository**. They are not
instructions for using the skill on your own projects.

## This repository is public

`github.com/SionVerhoef/cia402-motion` is world-readable and installed into other people's
setups. Assume every commit is permanent and already read by a stranger.

## Treat real machine data as if it were under NDA

Configurations, drive parameters, diagnostics dumps and code come from real machines
belonging to real customers. **Never commit anything that identifies a customer, a site, a
machine or a controller** — in files *and* in commit messages, changelog entries, eval
transcripts and issue text:

- Customer, site or end-user names, machine and serial numbers, project codes — including
  inside axis names, device names, comments and file paths
- IP addresses, AMS NetIDs, MAC addresses, credentials, licence keys
- Tuning parameters, setpoints, cycle times — commercially sensitive
- Safety configuration tied to one installation

**Anonymise by substitution, not by deletion.** Rename `Customer_A`, `Line1`, `Axis_X`;
the structure is what teaches, and it survives renaming. Naming a *product* (TwinCAT,
AX5000, EL7201) is fine; naming *whose* machine it is, is not.

## What you may use, and what you may not

**Research is not redistribution.** Read any source you lawfully can — Beckhoff InfoSys,
drive manuals, ETG and CiA specifications. Copyright protects expression, not facts: state
that a statusword bit means "fault"; do not paste the manual's paragraph or table about it.

- **Permissive** (MIT, BSD, Apache-2, 0BSD) — may ship. Copy the upstream `LICENSE` next to
  it and record the source in the same commit.
- **Copyleft** (GPL/LGPL) — do not vendor; it would relicense this skill. Ask first.
- **Proprietary** (InfoSys, vendor manuals, forums) — research only. Cite and link; reproduce
  no passages, tables, diagrams or screenshots.
- **Member-only specs** (ETG, CiA) — the technical facts can be stated independently; the
  document's text, tables and figures cannot, and the documents themselves never land here.

Manuals, specs and real recordings stay in `research/` (gitignored) or outside the repo.

## Everything here must apply to everybody

This is a general-purpose skill. Rules and examples must make sense to a reader with no
connection to the project they came from. Don't promote one shop's house style to the only
correct answer.

## If something private has already been committed

**Stop and tell the maintainer.** Do not quietly delete it in a follow-up commit: on a public
repo the old blob stays reachable in history on every clone and fork. Removing it needs a
history rewrite and a force-push, which is the maintainer's decision.
