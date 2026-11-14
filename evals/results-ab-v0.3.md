# A/B round v0.3: two replacement tasks

Run 2026-11-14 with `evals/run_cells.py --reps 3 --only log-a6bn-homing-mode-switch,vendor-nidec-rotary-table`,
Opus 5.5 (`claude-opus-5-5`) and Haiku 5.5 (`claude-haiku-5-5`), one model at a time. The skill
was snapshotted at `2cfbc84`, whose skill files are `main` at `be5b4b9`: only `evals/` differs.
Graded by `evals/judge.py` with Sonnet 5.5, as in v0.2. The verdicts below are the judge's. No
hand verdict was set. The other nine evals were not rerun: their v0.2 verdicts stand.

v0.2 (`results-ab-v0.2.md`) found `log-homing-to-csp-fault` and `units-endless-rotary-wrap` right
in all 24 answers of both arms on both models. Both were retired. Two tasks replace them, each
needing two or three independent points, one of them a vendor fact:

- `log-a6bn-homing-mode-switch`: two cycle logs from a Panasonic A6BN. Run A copies 0x6064 in
  the first cycle 0x6061 reads 8, but the A6BN's TxPDO objects are not valid for about 2 ms
  during a mode switch (the log shows 0), which gives Err24.0. Run B switches on bit 12 alone
  (0x1237) while the axis is still moving, which gives Err27.4. The decoy is a colleague who
  wants to raise the window and blames EMC.
- `vendor-nidec-rotary-table`: an index table ported to a Nidec SI-EtherCAT drive. Relative moves
  are refused while 0x60F2 sets a direction, and the 0x607B minimum is fixed at 0. The
  colleague's fix (0x60F2 = 0) lets absolute moves turn backwards.

## Verdicts

R right · P partly · W wrong, by the judge. Three repetitions each.

| Eval | Opus 5.5 skill | Opus 5.5 baseline | Haiku 5.5 skill | Haiku 5.5 baseline |
|---|---|---|---|---|
| log-a6bn-homing-mode-switch | RRR | RRR | RRR | RPR |
| vendor-nidec-rotary-table | RRR | PPP | **PPR** | PPW |

## What the round shows

**The Nidec task discriminates, and the Haiku skill arm can fail it.** No baseline answer knew
that SI-EtherCAT refuses relative moves while a direction is set: Opus blamed the bad 0x607B
range for the steps not running. Two Haiku skill answers had both Nidec facts, then cleared
0x60F2 and moved the forward-only rule into PLC-computed relative moves. The judge read that as
falling into the colleague's trap. This is a judgement call in the rubric: positive relative moves
also keep the table turning forwards while all motion goes through that code. Only the drive's own
guarantee is lost, for example for a recovery or maintenance move. A sentence on the Nidec page
saying to keep the direction and send absolute targets would probably close it.

**The A6BN log does not discriminate on Opus.** Opus without the skill worked out the invalid
read from the log alone (an axis cannot move 50 mm and back in 2 ms), and read 0x1237 correctly,
in all three answers. A log that shows the evidence lets a strong model deduce the cause without
the vendor fact. Haiku's baseline missed it once.

**The Opus skill arm is still 6/6.** Neither task made it fail, and it has failed none of the
eleven in v0.2 or v0.3. The next attempt should be a task whose answer is not on a single vendor page and must be put together from several.

## Grader

The regex checks agree with the judge on 11 of 12 Opus cells and 5 of 12 Haiku cells. The main
miss is on the Nidec point 3: an answer that names the backwards risk and absolute targets
passes the check, even when it then clears 0x60F2 itself. The A6BN checks also missed some
phrasings of the invalid read in both directions. The judge's verdict wins in `grade.py`.

## Audit and cost

Both audits were clean: no baseline cell used a tool but Write, every skill cell read `SKILL.md`,
and none read outside its cell and the snapshot.

| | Skill arm, per cell | Baseline, per cell |
|---|---|---|
| Opus 5.5 | 137k tokens, 85 s, $0.38 | 19k tokens, 72 s, $0.19 |
| Haiku 5.5 | 206k tokens, 59 s, $0.01 | 27k tokens, 47 s, $0.01 |

Judge $0.57 for 24 cells. The round cost about $4.

## Limits

- Three repetitions per cell. A difference of one P is noise.
- The judge reads the author's rubric, and the Nidec rubric's third point is a design preference
  stated above, not a profile rule.
- Run directories were scratch and are not kept.
