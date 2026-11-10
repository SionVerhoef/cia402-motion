#!/usr/bin/env python3
"""Have a different model grade every answer of a round against its eval's rubric.

    python3 evals/judge.py <run-dir> [--model claude-sonnet-5-5] [--only EVAL[,EVAL]]
                                     [--parallel 3]

The checks in grade.py and the hand read of v0.1 had one author: the agent that wrote the
evals, the skill and the expected answers. This is the independent read. A model that wrote
none of it, and is not one of the models under test, reads each answer with the eval's
prompt, expected output, traps and grading rule, and gives a verdict with its reasons. It
is not told which arm wrote the answer, and the cell path it could guess that from is not
in its prompt.

Each judge call is a headless Claude Code session with no tools, no settings, no MCP
servers and no session file, so it sees only the prompt. The verdict goes to judge.json in
the cell; grade.py then uses it over the checks and lists every cell where the two
disagree. A hand verdict.json still wins over both. Cells that already have a judge.json
are skipped, so a rerun resumes.

Standard library only, apart from the `claude` CLI itself.
"""

import argparse
import concurrent.futures
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from grade import answer_of  # noqa: E402

TIMEOUT = 900

INSTRUCTION = """You are grading one answer to a technical question about CiA 402 (DS402) servo
drives. You did not write the question, the reference answer or the answer. Grade the answer
strictly by the grading rule below.

- The reference answer is what the question's author checked against the sources. Where your
  own knowledge disagrees with a fact in it, the reference wins.
- An answer may be right in other words, with a different but equally valid fix, or with more
  than the reference has. Judge the substance, not the wording or the length.
- A trap is a mistake the question was built to catch. An answer that names a trap only to
  reject it has not fallen into it.
- Where the answer gives code, read the code itself: what it would send to the drive, and in
  which order. Prose that gets a rule right does not save code that breaks it.
- FB_Cia402Axis is a published function block that is tested against a simulated drive to
  keep the state-machine ordering rules internally. If the answer instantiates it, judge
  the code around it and how its inputs and outputs are wired; if it pastes it, the same.
- Verdicts: {verdicts}.

Reply with one JSON object and nothing after it:
{{"verdict": "<one of {verdict_list}>", "points": {{"<each point of the grading rule>": true or false}}, "why": "<two or three sentences>"}}

=== Question ===
{prompt}

=== Reference answer ===
{expected}

=== Traps ===
{traps}

=== Grading rule ===
{grading}

=== The answer to grade ===
{answer}
=== End of the answer ===
"""


def build_prompt(ev: dict, answer: str) -> str:
    guardrail = ev.get("scored") == "guardrail"
    verdicts = ("pass or fail, as the grading rule says" if guardrail
                else "R (right), P (partly) or W (wrong), as the grading rule says")
    return INSTRUCTION.format(
        verdicts=verdicts, verdict_list='"pass", "fail"' if guardrail else '"R", "P", "W"',
        prompt=ev["prompt"], expected=ev["expected_output"],
        traps="\n".join(f"- {t}" for t in ev.get("traps", [])), grading=ev["grading"],
        answer=answer.strip() or "(no answer)")


def parse(text: str, guardrail: bool):
    """The last JSON object in the reply that carries a valid verdict, stray text around it or not."""
    ok = {"pass", "fail"} if guardrail else {"R", "P", "W"}
    found = None
    for m in re.finditer(r"\{", text):
        try:
            obj, _ = json.JSONDecoder().raw_decode(text[m.start():])
        except ValueError:
            continue
        if isinstance(obj, dict) and obj.get("verdict") in ok:
            found = obj
    return found


def judge_cell(cell: Path, ev: dict, model: str) -> dict:
    guardrail = ev.get("scored") == "guardrail"
    work = cell / ".judge"
    work.mkdir(exist_ok=True)
    env = {"HOME": os.environ["HOME"], "PATH": os.environ["PATH"], "LANG": "C.UTF-8",
           "TERM": "dumb", "USER": os.environ.get("USER", ""), "TMPDIR": str(work)}
    cmd = ["claude", "-p", "--model", model, "--safe-mode", "--setting-sources", "",
           "--strict-mcp-config", "--disable-slash-commands", "--no-session-persistence",
           "--tools", "", "--output-format", "json"]
    try:
        proc = subprocess.run(cmd, cwd=work, env=env, input=build_prompt(ev, answer_of(cell)),
                              capture_output=True, text=True, timeout=TIMEOUT)
        out = json.loads(proc.stdout) if proc.stdout.strip() else {}
    except (subprocess.TimeoutExpired, ValueError) as e:
        return {"cell": cell, "error": type(e).__name__}
    obj = parse(out.get("result", ""), guardrail) if not out.get("is_error") else None
    if not obj:
        (work / "last-reply.txt").write_text(proc.stdout + proc.stderr)
        return {"cell": cell, "error": "no verdict in the reply"}
    obj.update(model=model, cost_usd=out.get("total_cost_usd", 0))
    (cell / "judge.json").write_text(json.dumps(obj, indent=2) + "\n")
    return {"cell": cell, "verdict": obj["verdict"], "cost": obj["cost_usd"]}


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("run_dir", type=Path)
    p.add_argument("--model", default="claude-sonnet-5-5")
    p.add_argument("--only", default="", help="comma-separated eval names")
    p.add_argument("--parallel", type=int, default=3)
    a = p.parse_args()
    if not shutil.which("claude"):
        sys.exit("the claude CLI is not on PATH")
    run = a.run_dir.resolve()
    manifest = json.loads((run / "MANIFEST.json").read_text())
    evals = {e["name"]: e for e in json.loads((HERE / "evals.json").read_text(encoding="utf-8"))["evals"]}
    only = {x for x in a.only.split(",") if x}
    todo = []
    for m in manifest:
        cell = run / m["cell"]
        if only and m["eval"] not in only:
            continue
        finished = (cell / "run.json").exists() and (cell / "run.json").stat().st_size > 0
        if finished and not (cell / "judge.json").exists():
            todo.append((cell, evals[m["eval"]]))
    print(f"judging {len(todo)} cell(s) with {a.model}")
    errors, cost = [], 0.0
    with concurrent.futures.ThreadPoolExecutor(a.parallel) as pool:
        for r in pool.map(lambda x: judge_cell(x[0], x[1], a.model), todo):
            rel = r["cell"].relative_to(run)
            if "error" in r:
                errors.append(f"{rel}: {r['error']}")
                print(f"  !! {rel}: {r['error']}", flush=True)
            else:
                cost += r["cost"] or 0
                print(f"  {r['verdict']:4s} {rel}", flush=True)
    print(f"judge cost ${cost:.2f}")
    if errors:
        print(f"{len(errors)} cell(s) without a verdict; rerun to retry them.")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
