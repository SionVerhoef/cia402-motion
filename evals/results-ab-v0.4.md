# A/B round v0.4: one program, three drives

Run 2026-11-14 with `evals/run_cells.py --reps 3 --only code-review-three-drives`, Opus 5.5
(`claude-opus-5-5`) and Haiku 5.5 (`claude-haiku-5-5`), one model at a time. The skill was
snapshotted at `10d9304`, whose skill files are `main` at `2f9b0ef`: only `evals/` differs.
This is before #47 changed `vendors/nidec.md`, a change that touches none of the task's five
points. Graded
by `evals/judge.py` with Sonnet 5.5. The verdicts below are the judge's. No hand verdict was set.
The other ten evals were not rerun.

v0.3 (`results-ab-v0.3.md`) left the Opus skill arm at 6/6, and `log-a6bn-homing-mode-switch`
did not discriminate on Opus: its log shows its own evidence. It is retired. Its replacement is
built so that no single page holds the answer. `code-review-three-drives` gives one generic
master program (enable, home, CSP, a PV jog, bit-13 supervision, pause by quick stop) that must
run on a STOBER SI6, a Panasonic A6BN and a Nidec M700. Each of five breaks sits on a different
vendor page:

- (A) A6BN: Err88.1 when enabled with 0x6060 = 0.
- (B) Nidec: no PV mode.
- (C) Nidec: 0x6065 defaults to 2³¹−1, so bit 13 never comes.
- (D) STOBER: quick stop always ends in Switch on disabled, so 0x000F does not resume.
- (E) A6BN: 0x6091/0x6092 written in OP take effect only at PreOP, power-on or homing.

Right needs four of the five.

## Verdicts

R right · P partly · W wrong, by the judge. Three repetitions each.

| Eval | Opus 5.5 skill | Opus 5.5 baseline | Haiku 5.5 skill | Haiku 5.5 baseline |
|---|---|---|---|---|
| code-review-three-drives | RRR | PPR | RRR | WWW |

Every skill answer, on both models, had all five points. The Nidec 0x6065 default was the point
the baselines missed most: one Opus answer had it, no Haiku answer did.

## A first run on a flawed prompt

The first version of the prompt said 0x6081/0x6083 set the homing speeds, which are
0x6099/0x609A. It also put the STOBER on its plain "CiA 402" application, where the page says
scaling is done in the master. One Haiku skill answer flagged both, and the judge marked it
partly right for "inventing breaks". The prompt was corrected (HiRes Motion, 0x6099/0x609A), and
the rubric now says that a break claimed in step 3 or 4 that is not real loses a point. Both
models were run again. Only the second run is reported above. The first run gave the same picture:
Opus RRR / PPP, Haiku PRR / WWW.

## What the round shows

**Spreading the answer over three pages did not make the Opus skill arm fail.** With the drives
named, every skill answer opened all three vendor pages and mapped each fact to its step. Asking
for more pages costs the skill arm tokens (249k per Opus cell, against 137k in v0.3), not
correctness.

**The task discriminates clearly**, more than any other in the set on Haiku: skill RRR, baseline
WWW. The Opus baseline scored PPR. Its R answer hedged every vendor claim ("probably", "verify").
It also claimed a break of its own in step 5 that the STOBER page contradicts (no PV on HiRes
Motion; the page lists mode 3). That claim is outside steps 3 and 4, so the rubric does not count
it. A stricter judge would have marked it P.

**Where the Opus skill arm could still fail.** In v0.2 to v0.4 it has failed nothing whose facts
are on a page of the skill once the vendor is named. The only skill-arm failures so far (Haiku on
`nc-and-fb-one-drive` and `vendor-nidec-rotary-table`) came from judgement beyond the page. Tasks
that could still make Opus fail are of two kinds. In the first, the vendor is not named and must
be found from the symptom or from 0x1018. In the second, the needed fact is missing from the
skill, which measures coverage and points at what to add.

## Grader

The regex checks agree with the judge on 11 of 12 cells. The miss is the hedged Opus baseline
answer above, where the checks gave P.

## Audit and cost

Both audits were clean.

| | Skill arm, per cell | Baseline, per cell |
|---|---|---|
| Opus 5.5 | 249k tokens, 160 s, $0.80 | 34k tokens, 148 s, $0.40 |
| Haiku 5.5 | 299k tokens, 145 s, $0.03 | 45k tokens, 86 s, $0.01 |

Both runs together, judge included, cost about $8.

## Limits

- Three repetitions per cell. A difference of one P is noise.
- One prompt fix came after a first run. Both runs and the fix are stated above.
- Run directories were scratch and are not kept.
