# Evals

Does this skill change what an agent does? Every eval can run twice: once by an agent told
to read and follow `SKILL.md`, once by an agent told to answer from its own knowledge. The
difference is the only number worth anything. A skill that scores 100% while the baseline
also scores 100% has measured nothing.

```bash
python3 evals/selftest.py                                   # the grader first (CI runs it)
python3 evals/run_cells.py /tmp/ab-opus --model claude-opus-5-5 --reps 3   # the A/B round
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

## The sets

- `candidates.json`: the scouting set, 14 tasks asked without the skill to find where a model
  is wrong unaided. Graded by hand; verdicts in `results-scouting.md`.
- `evals.json`: the A/B set. Six scouting tasks some model got wrong, and four aimed at what
  scouting found: ordering errors that only show in code, vendor facts, and the `pdo` verb.
  Each eval carries its prompt, the right answer in our own words, the traps, and a rubric
  for right, partly and wrong. `guardrail-sto` is pass/fail, must pass in every skill cell,
  and never counts as evidence the skill helps.
- `trigger-evals.json`: whether the `description` makes the skill fire. See below.

## Grading

`grade.py` turns each answer into right, partly or wrong by its eval's rubric, using one
regular-expression check per point of the rubric. Negative checks are refusal-aware: the best
answers name a trap in order to reject it ("do not swap the supply"), so a claim only counts in
a sentence that does not deny or rebut it. The checks detect that a point was made, not that it
was made well, and some rules are control flow no pattern can see (does the reset release bit
7, does a stop avoid T9). So every answer to the code task, every guardrail answer, and every
cell where the checks look doubtful is read by hand; a `verdict.json` in the cell
(`{"verdict": "P", "why": "..."}`) wins over the checks, and the report lists each override.

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
