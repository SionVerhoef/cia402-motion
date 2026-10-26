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
writes `REPORT.txt`: cost per arm, and an audit that flags a baseline cell that read the
skill or ran a shell command outside its cell, a skill cell that did not read `SKILL.md`, a
write outside a cell, and a cell with no `answer.md`. The run directory must be outside
every git repository. Rerunning the same command resumes. Its docstring says why each
isolation flag is there.

`candidates.json` holds the scouting set: each task's prompt, the right answer in our own
words, the traps to look for, and how to grade it as right, partly or wrong. Scouting is
graded by hand. `results-scouting.md` has the verdicts and what follows from them.

The baseline arm is told not to read the skill and gets only Write and Bash, so it can do
hex arithmetic but cannot go looking for this repository. It is not otherwise handicapped,
and the prompt tells it the subject. Telling it nothing would measure prompt luck instead.
