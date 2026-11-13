# Evals

Does this skill change what an agent does? Every eval can run twice: once by an agent told
to read and follow `SKILL.md`, once by an agent told to answer from its own knowledge. The
difference is the only number worth anything. A skill that scores 100% while the baseline
also scores 100% has measured nothing.

```bash
python3 evals/selftest.py                                   # the grader first (CI runs it)
python3 evals/run_cells.py /tmp/ab-opus --model claude-opus-5-5 --reps 3   # the A/B round
python3 evals/judge.py /tmp/ab-opus                         # the independent read (Sonnet 5.5)
python3 evals/grade.py /tmp/ab-opus                         # right / partly / wrong per cell
```

`run_cells.py` snapshots the skill at `--ref` (default `HEAD`) minus `evals/`, lays the cells
out with `prepare_run.py`, runs each in its own isolated headless Claude Code session, and
writes `REPORT.txt`: cost per arm, and an audit that flags a failed session, a baseline
cell that used any tool but Write, a skill cell that did not read `SKILL.md` or read outside
its cell and the snapshot, a write outside a cell, and a cell with no `answer.md`. It lists
every shell command a skill cell ran, to be read. The run directory must be outside every
git repository and holds one model; rerunning the same command resumes, retrying failed
cells. Its docstring says why each isolation flag is there.

The baseline arm is told not to read the skill and gets the Write tool only, so it cannot go
looking for this repository, which is public. It is not otherwise handicapped, and the prompt
tells it the subject. Telling it nothing would measure prompt luck instead.

`--arms web_baseline` adds a third arm with WebSearch and WebFetch, as a user's agent could
have. It is told to stay off this repository, and the report flags any request or tool result
that names `cia402-motion`. Results: `results-web-baseline.md`. Run one model at a time: two
runs side by side once corrupted the shared Claude Code config file.

## The sets

- `candidates.json`: the scouting set, 14 tasks asked without the skill to find where a model
  is wrong unaided. Graded by hand; verdicts in `results-scouting.md`.
- `evals.json`: the A/B set. Six scouting tasks some model got wrong, one code task aimed at
  the ordering errors scouting found, and, since v0.2, three tasks the skill can fail as well:
  an NC axis and a PLC block both writing one drive, a fault traced through a cycle log, and an
  endless rotary axis that overruns the 32-bit position. v0.2 retired `pdo-two-axis` and
  `canopen-bringup`, right in every answer of both arms in v0.1. Each eval carries its prompt, the right answer in our own words, the traps, and a rubric
  for right, partly and wrong. `guardrail-sto` is pass/fail, must pass in every skill cell,
  and never counts as evidence the skill helps.
- `trigger-evals.json`: whether the `description` makes the skill fire. See below.

## Grading

`grade.py` turns each answer into right, partly or wrong by its eval's rubric, using one
regular-expression check per point of the rubric. Negative checks are refusal-aware: the best
answers name a trap in order to reject it ("do not swap the supply"), so a claim only counts in
a sentence that does not deny or rebut it. The checks detect that a point was made, not that it
was made well, and some rules are control flow no pattern can see (does the reset release bit
7, does a stop avoid T9). So every answer is also read by `judge.py`.

`judge.py` is the independent read. The checks, the evals and the expected answers have one
author, and in v0.1 the hand read was that author too. The judge is a model that wrote none of
it and is not under test (Sonnet 5.5 by default, `--model` to change). It gets the eval's
prompt, expected answer, traps and rubric and the answer, not the arm or the cell path, runs
with no tools and no settings, and writes `judge.json` into the cell. `grade.py` takes the
judge's verdict over the checks and lists every cell where they disagree: those are the ones
to read. A `verdict.json` in the cell (`{"verdict": "P", "why": "..."}`) wins over both, and
the report lists it.

`selftest.py` grades the grader before any agent runs. Each eval has a good answer, which must
grade right, and trapped answers, each labelled with the verdict it must get; most repeat an
error the scouting round actually saw. An empty answer must grade wrong. The answers and the
patterns have the same author, so this is a floor: it catches checks that can never pass,
checks everyone passes, and negative checks that punish the refutation, not whether the checks
measure the right thing.

## Trigger evals

`trigger-evals.json` holds queries the skill should take and near-misses that belong to a
sibling skill or to none: a TwinCAT NC axis (twincat-motion), AL status codes and working
counters (ethercat-diagnostics), an ESI file (ethercat-esi), plain Structured Text
(twincat-st), and other drive profiles and buses. It is the input format of skill-creator's
`run_eval.py`, run through `run_trigger.py`, which gives every call its own throwaway project:

```bash
export SKILL_CREATOR_DIR=<path to the skill-creator skill folder>
python3 evals/run_trigger.py check --model <id> --timeout 180 --num-workers 5
```

A query counts as triggered only when the model's first tool call loads the skill. The calls
still load the operator's global Claude Code settings, so other installed skills compete, as
they would in real use.

**Results for v0.1.0** (2026-10-29, Opus 5.5, three runs per query). With "units and gearing" in
the description, the user-units query fired in only 1 of 3 runs, so the description now names
0x608F, 0x6091 and 0x6092. With that description, the 13 queries the skill should take fired in
38 of 39 runs. The 11 near-misses fired in 2 of 33, both on the TwinCAT NC axis query, which
fired 1 of 3 in the first run. That query is a real borderline: `MC_Power.Status` never going
TRUE is where twincat-motion hands a drive that will not enable to this skill, and twincat-motion
was not installed to compete. Nothing else fired in either run.

**Haiku 5.5, and the description that followed** (2026-11-06, three runs per query, three
workers). With the description above, Haiku 5.5 took the skill in only 11 of the 39 runs it
should have, and none of the near-misses: it answered from its own knowledge, which is where the
A/B evals found it wrong. A description that begins "Load before answering any question about a
CiA 402 / DS402 … drive" and says why (vendors depart from the profile in ways that look
standard) fired in 38 of 39 on Haiku, but on Opus it also took a TwinSAFE logic query 3 of 3,
the AX5000/SoE query 1 of 3 and the NC axis query 2 of 3. Naming SERCOS/SoE drives and safety
PLC logic under "Not for" gave the description now in `SKILL.md`:

| Description | Haiku 5.5 should / near-miss | Opus 5.5 should / near-miss |
|---|---|---|
| v0.1 ("Use for the CiA 402 …") | 11/39 · 0/33 | 38/39 · 2/33 |
| "Load before answering …" | 38/39 · 0/33 | 39/39 · 6/33 |
| the same, with SoE and safety PLC logic excluded | 37/39 · 0/33 | 39/39 · 2/33 |

The two exclusions were written after those near-misses fired, so the near-miss score of the
last row is measured on the queries it was tuned to. New near-misses would confirm it. Its
Opus misfires are again the NC axis query only.

**Brand names out of the description** (2026-11-08, three runs per query, three workers). The
description listed the vendors with pages, which could not grow with every page, and every
vendor query also named CiA 402 objects, so nothing showed the names helped. Four queries that
name only a product were added (Unidrive M700 with SI-EtherCAT, EPOS4, Synapticon SOMANET, Omron
1S), and the list was replaced by "any vendor's drive, with checked pages on where named drive
families depart from it":

| Description | Haiku 5.5 product-only · should · near-miss | Opus 5.5 product-only · should · near-miss |
|---|---|---|
| with the brand list | 8/12 · – · – | 12/12 · – · – |
| without it (now in `SKILL.md`) | 10/12 · 49/51 · 0/33 | 12/12 · 51/51 · 2/33 |

The names did not help: Nidec, never in the list, fired in every run, and Haiku missed the
Synapticon query 3 of 3 with Synapticon named. The Haiku difference is within three-run noise.
Opus misfires are the NC axis query again.

The profile covers frequency inverters too (VL is their mode), so the description then said
"servo, stepper or frequency-inverter (VFD) drive" and named VL among the modes, and one
should-trigger query asks about an inverter in velocity mode stuck in Switch on disabled. The
worry was the Modbus VFD and SINAMICS/PROFINET near-misses. Same day and setup:

| Description | Haiku 5.5 should · near-miss | Opus 5.5 should · near-miss |
|---|---|---|
| with VFD and VL (now in `SKILL.md`) | 52/54 · 0/33 | 54/54 · 3/33 |

The inverter query fired 3 of 3 on both, the Modbus and PROFINET queries 0 of 3 on both. All
three Opus misfires are the NC axis query, 3 of 3 this time: still the one borderline.

**New near-misses** (2026-11-10, three runs per query, three workers). Eight near-misses the
description was never tuned on were added: NC position-lag parameters, an SDO abort code, an
ESI import error, CIP Motion homing, motor sizing, a Pilz SLS setup, CODESYS SoftMotion homing
and a notch filter. Same description:

| Description | Haiku 5.5 should · old near-miss · new near-miss | Opus 5.5 should · old near-miss · new near-miss |
|---|---|---|
| as in `SKILL.md` | 50/54 · 0/33 · 1/24 | 54/54 · 3/33 · 5/24 |

The near-miss score did not hold on unseen queries on Opus: CODESYS SoftMotion `MC_Home` fired
3 of 3 (Haiku 1 of 3), the notch filter 2 of 3. The description excludes TwinCAT NC and MC_
blocks but not SoftMotion, and does not mention loop tuning. The old misfires are the NC axis
query again. Haiku's four misses are four different should-trigger queries, 2 of 3 each.

**SoftMotion and loop tuning excluded** (2026-11-13, three runs per query, three workers). "Not
for" now names CODESYS SoftMotion axes and servo loop tuning. Four more near-misses it was never
tuned on were added: a SoftMotion cam, a SoftMotion modulo move, an AKD hum after autotuning and
a velocity-loop overshoot.

| Description | Haiku 5.5 should · old · 11-10 · new near-miss | Opus 5.5 should · old · 11-10 · new near-miss |
|---|---|---|
| as in `SKILL.md` | 50/54 · 0/33 · 0/24 · 0/12 | 52/54 · 2/33 · 0/24 · 0/12 |

The eight 2026-11-10 near-misses went from 5 of 24 to none on Opus, and the four new ones did not
fire on either model. The Opus misfires are the NC axis query again (2 of 3). Its two misses are
the EL7211-9014 query, 1 of 3; run again six times with this description and six with the one
before, it fired 6 of 6 with both, so that was noise. Haiku missed Synapticon 3 of 3, as before,
and the python-canopen query once.

The A/B results are in `results-ab.md` (v0.1) and `results-ab-v0.2.md`.

A first attempt that ran four checks at once timed
out most session start-ups and scored them as misses; run one check at a time.
