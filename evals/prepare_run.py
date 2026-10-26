#!/usr/bin/env python3
"""Lay out a run directory: one folder per eval / arm / repetition, each with the
exact prompt.

    python3 evals/prepare_run.py <run-dir> [--reps N] [--skill PATH/TO/SKILL.md]
                                 [--spec evals/candidates.json]

Then run one agent per cell (run_cells.py does that). Each agent writes its reply to
`answer.md` in its cell.

Why the arms are worded the way they are: the point is to measure the skill, so the
baseline arm must be kept from reading it while still being told what kind of question
it is. Telling the baseline nothing at all measures prompt luck instead.

The prompts name SKILL.md by absolute path: cells live outside this repository, where a
bare `SKILL.md` does not resolve. Pass `--skill` to point at an exported copy (run_cells.py
passes a `git archive` of the skill minus evals/), so the with-skill agent cannot wander
into the expected answers.

Standard library only.
"""

import argparse
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent

ARM_INSTRUCTION = {
    "with_skill": (
        "Read {skill} and follow it. Load whatever reference files it routes you to, and "
        "use whatever it ships in scripts/ if they apply. Then answer the request below."
    ),
    "without_skill": (
        "Answer the request below from your own knowledge. Do NOT read {skill} or anything "
        "under references/, scripts/ or templates/ - this run is the baseline it is "
        "measured against."
    ),
}

CELL_TEMPLATE = """# {eval_name} / {arm} / {rep}

## Instruction to the agent

{instruction}

Write your complete reply to `answer.md` in this directory. That file is what gets graded.

## Request

{prompt}
"""


def main():
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("run_dir", type=Path)
    p.add_argument("--reps", type=int, default=3)
    p.add_argument("--skill", type=Path, default=ROOT / "SKILL.md")
    p.add_argument("--spec", type=Path, default=HERE / "evals.json")
    a = p.parse_args()

    spec = json.loads(a.spec.read_text(encoding="utf-8"))
    arms = spec.get("run", {}).get("arms", ["with_skill", "without_skill"])
    skill = str(a.skill.resolve())
    manifest = []
    for ev in spec["evals"]:
        for arm in arms:
            for n in range(1, a.reps + 1):
                cell = a.run_dir / ev["name"] / arm / f"rep{n}"
                cell.mkdir(parents=True, exist_ok=True)
                (cell / "PROMPT.md").write_text(CELL_TEMPLATE.format(
                    eval_name=ev["name"], arm=arm, rep=f"rep{n}",
                    instruction=ARM_INSTRUCTION[arm].format(skill=skill),
                    prompt=ev["prompt"],
                ), encoding="utf-8")
                manifest.append({
                    "eval": ev["name"], "arm": arm, "rep": n,
                    "category": ev.get("category", ""),
                    "scored": ev.get("scored", "discriminating"),
                    "cell": str(cell.relative_to(a.run_dir)),
                })

    (a.run_dir / "MANIFEST.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"prepared {len(manifest)} cells under {a.run_dir}")
    print(f"  {len(spec['evals'])} evals x {len(arms)} arms x {a.reps} reps")


if __name__ == "__main__":
    main()
