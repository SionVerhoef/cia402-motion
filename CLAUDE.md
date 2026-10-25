# Working on this repository

These rules apply to anyone — human or agent — **editing this repository**. They are not
instructions for using the skill on your own projects, where your drives are your own.

## This repository is public

`github.com/SionVerhoef/cia402-motion` is world-readable, mirrored by anyone who clones it,
and installed into other people's setups. Assume every commit is permanent and already read
by a stranger.

## Treat real drive data as if it were under NDA

Parameter dumps, object-dictionary reads, PDO mappings and code come from real drives on real
machines belonging to real customers. Handle all of it as confidential by default — not only
what someone explicitly marked as such.

**Never commit anything that identifies a customer, a site, a machine or a drive.** That
includes, in files *and* in commit messages, changelog entries, eval transcripts and issue
text:

- **Customer, site or end-user names**, machine numbers, project codes — including inside
  axis names, device names, comments and file paths
- **Drive and motor serial numbers**, and the identity object `0x1018` read from a real
  device
- **AMS NetIDs, IP addresses, MAC addresses, hostnames, credentials, licence keys**
- **Parameter files and configuration-tool exports** from any vendor — they carry serial
  numbers and the complete tuning of one axis. Never commit them raw.
- **Tuning and process data** — loop gains, current and following-error limits, profile
  velocities and accelerations, setpoints, cycle times. Commercially sensitive.
- **Safety configuration tied to one installation** — STO wiring, safe-torque parameters

## Anonymise by substitution, not by deletion

The point is to remove identity while keeping the teaching value. Renaming a customer to
`Customer_A` and an axis to `Axis_X`, and replacing a serial number with `00000000`, costs
nothing and keeps every signal that matters — which state the drive is stuck in, which
controlword it was sent, which error code it raised.

**Names are stand-ins; structure is real.** If a finding only makes sense with the original
names in place, describe it in prose instead. Naming a *product* is fine and often
necessary: a drive family or a firmware version describes something anyone can buy. Naming
*whose* machine it is, is not.

**Use placeholders that identify nothing:** AMS NetId `1.2.3.4.1.1`, IP addresses from
`192.0.2.0/24`, MAC addresses from `00:00:5E:00:53:xx`. CI runs `scripts/check_private.py`
and fails on any other NetId, IP or MAC it finds. It cannot recognise a customer name or a
serial number — that part is on you.

## What you may use, and what you may not

**Research is not redistribution.** Read any source you lawfully can — vendor drive manuals,
the CiA 402 / IEC 61800-7 profile, application notes. Copyright protects expression, not
facts: state that statusword bit 3 means "fault" and that controlword `0x0080` resets it; do
not paste the manual's paragraph, state diagram or object table.

- **Permissive** (MIT, BSD, Apache-2, 0BSD) — may ship. Copy the upstream `LICENSE` next to
  it and record the source in the same commit.
- **Copyleft** (GPL/LGPL) — do not vendor; it would relicense this skill. Ask first.
- **Proprietary** (vendor manuals, application notes, forums) — research only. Cite and
  link; reproduce no passages, tables, diagrams or screenshots.
- **Paid or member-only specs** (CiA, IEC) — the technical facts can be stated
  independently; the document's text, tables and figures cannot, and the documents
  themselves never land here.

Read the licence from the upstream `LICENSE` file, never a GitHub badge. A citation is not
permission. Manuals, specs and real parameter dumps stay in `research/` (gitignored) or
outside the repo.

## Everything here must apply to everybody

This skill covers the CiA 402 profile on any vendor's drive. Keep the standard objects
(`0x6040`, `0x6041`, `0x6060` …) separate from manufacturer-specific ones (`0x2000`–`0x5FFF`),
and label every vendor-specific behaviour with the vendor it was observed on. Don't present
one vendor's interpretation as the profile, and don't write a preference as a rule without
saying so.

## If something private has already been committed

**Stop and tell the maintainer.** Do not quietly delete it in a follow-up commit: on a public
repo the old blob stays reachable in history on every clone and fork. Removing it needs a
history rewrite and a force-push, which is the maintainer's decision.
