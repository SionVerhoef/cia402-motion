# Evals

Does this skill change what an agent does? Every eval can run twice: once by an agent told
to read and follow `SKILL.md`, once by an agent told to answer from its own knowledge. The
difference is the only number worth anything. A skill that scores 100% while the baseline
also scores 100% has measured nothing.

```bash
# scouting: the baseline alone, one repetition, one run directory per model
python3 evals/run_cells.py /tmp/scout-opus --model claude-opus-5-5 \
    --spec evals/candidates.json --arms without_skill --reps 1
```

`run_cells.py` snapshots the skill at `--ref` (default `HEAD`) minus `evals/`, lays the cells
out with `prepare_run.py`, runs each in its own isolated headless Claude Code session, and
writes `REPORT.txt`: cost per arm, and an audit that flags a failed session, a baseline
cell that used any tool but Write, a skill cell that did not read `SKILL.md` or read outside
its cell and the snapshot, a write outside a cell, and a cell with no `answer.md`. It lists
every shell command a skill cell ran, to be read. The run directory must be outside every
git repository and holds one model; rerunning the same command resumes, retrying failed
cells. Its docstring says why each isolation flag is there.

`candidates.json` holds the scouting set: each task's prompt, the right answer in our own
words, the traps to look for, and how to grade it as right, partly or wrong. Scouting is
graded by hand. `results-scouting.md` has the verdicts and what follows from them.

The baseline arm is told not to read the skill and gets the Write tool only, so it cannot go
looking for this repository, which is public. It is not otherwise handicapped, and the prompt
tells it the subject. Telling it nothing would measure prompt luck instead.
