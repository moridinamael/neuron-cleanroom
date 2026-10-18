"""Launch the blind agent in a sealed room as a headless Claude Code process and record everything.

  python -m cleanroom.launch --room ../rooms/L14_N2222 --run runs/2026-11-01_bonsai1_L14_N2222 [--model claude-opus-5-5]

Writes <run>/transcript.jsonl (every message and tool call, stream-json) and <run>/stderr.txt.
Afterwards: python -m cleanroom.audit --run <run>, then python -m cleanroom.collect --run <run>.

Before launching, commit your own predictions about what the agent will find (<run>/predictions.json)
in this repo, so they are pre-registered too.
"""
import argparse
import json
import os
import subprocess
from pathlib import Path

PROMPT = ("Read BRIEF.md and README.md in this folder, then carry out the brief from start to finish. You are working "
          "autonomously: nobody is available to answer questions, so make reasonable decisions yourself and keep going "
          "until REPORT.md and summary.json are written and committed.")
TOOLS = "Bash,Read,Edit,Write,Glob,Grep,Agent,NotebookEdit"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--room", required=True)
    ap.add_argument("--run", required=True)
    ap.add_argument("--model", default="claude-opus-5-5")
    ap.add_argument("--claude", default="claude", help="path to the Claude Code CLI")
    a = ap.parse_args()
    room, run = Path(a.room).resolve(), Path(a.run).resolve()
    if not (run / "predictions.json").exists():
        print("note: no predictions.json in the run folder; commit your expectations first if you want them pre-registered")
    cmd = [a.claude, "-p", PROMPT, "--model", a.model, "--setting-sources", "project", "--strict-mcp-config",
           "--allowedTools", TOOLS, "--output-format", "stream-json", "--verbose"]
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    with open(run / "transcript.jsonl", "w", encoding="utf-8") as out, open(run / "stderr.txt", "w", encoding="utf-8") as err:
        rc = subprocess.run(cmd, cwd=room, stdout=out, stderr=err, env=env).returncode
    meta = json.loads((run / "manifest.json").read_text(encoding="utf-8")) if (run / "manifest.json").exists() else {}
    meta["launch"] = {"model": a.model, "flags": cmd[3:], "exit_code": rc}
    (run / "manifest.json").write_text(json.dumps(meta, indent=1), encoding="utf-8")
    print(f"agent exited with {rc}; transcript in {run / 'transcript.jsonl'}")


if __name__ == "__main__":
    main()
