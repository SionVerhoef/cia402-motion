#!/usr/bin/env python3
"""Run skill-creator's trigger evaluation or description optimizer, with every
`claude -p` call isolated in a throwaway project of its own.

    python3 evals/run_trigger.py check    --skill-creator DIR --model <id> [run_eval options]
    python3 evals/run_trigger.py optimize --skill-creator DIR --model <id> [run_loop options]

DIR is the skill-creator skill folder (the one holding scripts/run_eval.py); it can
also come from $SKILL_CREATOR_DIR. --eval-set defaults to evals/trigger-evals.json and
--skill-path to this repository. `check` scores the current description once;
`optimize` also rewrites it. Neither touches SKILL.md — copy a winner in by hand.

What the stock scripts get wrong, and this wrapper fixes:

  * Every parallel worker writes its temporary command into one shared
    .claude/commands/ folder, so each session sees its siblings' identical copies,
    plus any a killed run left behind. A trigger of a sibling's copy scores as a
    miss: the first full optimizer run of the sibling skill twincat-st, where this
    wrapper comes from, reported 0% recall for that reason.
  * Each call leaves a transcript folder in the operator's Claude Code project
    history. The wrapper deletes the one its call created.
  * Run from inside this repository, every call would also load its CLAUDE.md,
    which talks about CiA 402 drives and biases the queries toward triggering.

Starting a session can take 40-50 s, so pass --timeout 180 and keep --num-workers
around 5; the default 30 s can time every call out and score it as a miss.

Known limit: the calls still load the operator's global Claude Code settings, so
other installed skills compete with this one, as they would in real use.
"""

import inspect
import os
import re
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HISTORY = Path.home() / ".claude" / "projects"
_stock = None


def isolated(*a, **kw):
    """The stock run_single_query, pointed at a fresh project root of its own."""
    bound = inspect.signature(_stock).bind(*a, **kw)
    root = tempfile.mkdtemp(prefix="cia402-trigger-")
    try:
        (Path(root) / ".claude").mkdir()
        bound.arguments["project_root"] = root
        return _stock(*bound.args, **bound.kwargs)
    finally:
        shutil.rmtree(root, ignore_errors=True)
        # Claude Code names a project's history folder after its path.
        shutil.rmtree(HISTORY / re.sub(r"[^A-Za-z0-9]", "-", str(Path(root).resolve())),
                      ignore_errors=True)


def main() -> None:
    if len(sys.argv) < 2 or sys.argv[1] not in ("check", "optimize"):
        sys.exit(__doc__)
    mode, args = sys.argv[1], sys.argv[2:]
    creator = os.environ.get("SKILL_CREATOR_DIR", "")
    if "--skill-creator" in args:
        i = args.index("--skill-creator")
        creator = args[i + 1]
        del args[i:i + 2]
    if not (Path(creator) / "scripts" / "run_eval.py").exists():
        sys.exit("point --skill-creator (or $SKILL_CREATOR_DIR) at the skill-creator skill "
                 "folder, the one holding scripts/run_eval.py")
    if "--eval-set" not in args:
        args += ["--eval-set", str(ROOT / "evals" / "trigger-evals.json")]
    if "--skill-path" not in args:
        args += ["--skill-path", str(ROOT)]

    sys.path.insert(0, str(Path(creator).resolve()))
    import scripts.run_eval as run_eval
    import scripts.run_loop as run_loop

    global _stock
    _stock = run_eval.run_single_query
    # The queries run in worker processes, which receive this function by name.
    # Registered under the stock name, a worker resolves it to the patched module
    # attribute; a function nested in main() cannot be sent at all, and every query
    # then fails and silently scores as "did not trigger".
    isolated.__module__ = run_eval.__name__
    isolated.__qualname__ = "run_single_query"
    run_eval.run_single_query = isolated

    # Results and the eval set resolve before leaving: the calls run from a neutral
    # directory, not from inside this repository.
    for flag in ("--eval-set", "--skill-path", "--report", "--results-dir"):
        if flag in args:
            i = args.index(flag) + 1
            if args[i] != "none":
                args[i] = str(Path(args[i]).resolve())
    neutral = tempfile.mkdtemp(prefix="cia402-trigger-cwd-")
    os.chdir(neutral)
    sys.argv = [f"run_trigger.py {mode}"] + args
    try:
        (run_eval if mode == "check" else run_loop).main()
    finally:
        os.chdir(ROOT)
        shutil.rmtree(neutral, ignore_errors=True)


if __name__ == "__main__":
    main()
