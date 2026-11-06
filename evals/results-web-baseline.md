# Web-search baseline (v0.2)

The A/B round in `results-ab.md` gave the baseline the Write tool only, so it could not look
anything up. The skill's lead came from vendor facts, and an agent that can search might find
them on its own. This round asks whether the lead survives a baseline with WebSearch and
WebFetch.

Run 2026-11-03 to 2026-11-06 with `evals/run_cells.py --arms web_baseline --reps 3` on the
five vendor, porting and triage tasks of `evals.json`, on Opus 5.5 (`claude-opus-5-5`) and
Haiku 5.5 (`claude-haiku-5-5`). The arm has Write, WebSearch and WebFetch. It is told to stay
off the skill and its public repository, and the audit flags any request, and any tool result,
that names `cia402-motion`. None did. Graded with `grade.py`. The verdicts that decide the
comparison were checked by reading the answers (below).

The skill and Write-only columns are the ones from `results-ab.md`, measured on the same tasks
and prompts. They were not rerun.

## Verdicts

R right · P partly · W wrong. Three repetitions each.

| Eval | Opus skill | Opus Write only | Opus web | Haiku skill | Haiku Write only | Haiku web |
|---|---|---|---|---|---|---|
| vendor-negative-homing | RRR | RRR | RRR | RRR | PPR | RRR |
| porting-epos4-nanotec | RRR | PPP | PPP | RRR | PWP | PPP |
| triage-epos4-bit4 | RRR | RRR | RRR | RRR | PWR | WWP |
| vendor-el72x1-profile | RRR | PPP | RPR | RRR | PPP | RPR |
| vendor-omron-1s | RRR | PRP | PPR | RRR | PPP | PPR |
| **Score** (R = 1, P = ½) | **15** | **11 (73%)** | **12 (80%)** | **15** | **8 (53%)** | **9.5 (63%)** |

## What the answers show

**Search closes a little of the gap, not most of it.** It adds one point on Opus and one and a
half on Haiku. The skill's lead on these tasks goes from 4 to 3 on Opus and from 7 to 5.5 on
Haiku.

**It helps where a vendor page answers the question.** The EL72x1's DS402 route turned up in
two of three answers on each model, and Haiku got the negative homing methods right every
time. On the Omron 1S, one answer per model corrected the false premise that 0x6091 does not
exist. Of the others, the one read by hand (Opus) found 0x6091 in a manual extract and still
hedged: "if your drive still reports object does not exist…".

**It does not help where the trap is a vendor's departure from the profile.** Every porting
answer on both models missed that the Nanotec NP5 leaves Quick stop active for Switch on
disabled. The Opus answers still told the user to set 0x605A = 6 on the NP5, which allows 0–2
only (the same error as without search). On the EPOS4 triage, search made Haiku worse. It
found a vendor's DS402 page that defines bit 4 as "DC-link voltage present", applied it to the
EPOS4, where bit 4 means the power stage is on and is 0 in Ready to switch on by design, and
sent the engineer after the supply in two of three answers.

**Cost.** A web cell cost $0.27 on Opus and $0.05 on Haiku, against $0.35 and $0.02 for a skill
cell in `results-ab.md`. The answers took about as long.

## Limits

- Three repetitions per cell, as before. One P is noise.
- Several manual sites refused fetches (Access Denied, an encrypted PDF). A user who downloads
  the manual by hand and pastes it in has more than this arm had.
- The checks, the expected answers and this reading have one author, as in `results-ab.md`.
- Three Opus cells failed the first time on a corrupted read of the shared Claude Code config
  file: two runs had been started side by side, six sessions at once. They were rerun alone.
  Run the models one after another.
