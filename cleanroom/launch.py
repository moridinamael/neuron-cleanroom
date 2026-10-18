"""Launch the blind agent in a sealed room as a headless process and record everything.

  python -m cleanroom.launch --room ../rooms/L14_N2222 --run runs/<run> [--agent claude|codex] [--model …]

claude: Claude Code (`claude -p`), project settings only (the room's seal), no MCP servers.
codex:  Codex (`codex exec --json`) with a FRESH, throwaway CODEX_HOME holding only the login, so no
        memories, plugins or project history come along; workspace-write sandbox (no network) and
        no approval prompts. On Windows the sandbox blocks writes outside the room but NOT reads, so
        for Codex the audit is the only check on reads (it flags any path outside the room).

Writes <run>/transcript.jsonl and <run>/stderr.txt. Commit <run>/predictions.json before launching;
its commit is recorded in the manifest. Afterwards: audit, collect, export, remove_room.
"""
import argparse
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

PROMPT = ("Read BRIEF.md and README.md in this folder, then carry out the brief from start to finish. You are working "
          "autonomously: nobody is available to answer questions, so make reasonable decisions yourself and keep going "
          "until REPORT.md and summary.json are written and committed.")
TOOLS = "Bash,Read,Edit,Write,Glob,Grep,Agent,NotebookEdit"


def codex_home():
    """A clean CODEX_HOME: only auth.json is copied from the user's real one."""
    real = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex"))
    base = Path.home() / ".cleanroom-codex"  # not under Temp: Codex refuses to install its helpers there
    base.mkdir(exist_ok=True)
    home = Path(tempfile.mkdtemp(prefix="home-", dir=base))
    shutil.copy2(real / "auth.json", home / "auth.json")
    cfg = ('model_reasoning_effort = "high"\napproval_policy = "never"\nsandbox_mode = "workspace-write"\n'
           '[sandbox_workspace_write]\nnetwork_access = false\n')
    if os.name == "nt":
        cfg += '[windows]\nsandbox = "unelevated"\n'  # Windows: commands are refused without this
    # macOS and Linux need nothing extra: Codex's own sandbox (Seatbelt / Landlock) enforces workspace-write
    (home / "config.toml").write_text(cfg, encoding="utf-8")
    return home


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--room", required=True)
    ap.add_argument("--run", required=True)
    ap.add_argument("--agent", choices=["claude", "codex"], default="claude")
    ap.add_argument("--model", default=None, help="claude default: claude-opus-5-5; codex default: its own")
    ap.add_argument("--claude", default="claude")
    a = ap.parse_args()
    room, run = Path(a.room).resolve(), Path(a.run).resolve()
    here = Path(__file__).resolve().parents[1]
    pred = (run / "predictions.json").relative_to(here).as_posix() if (run / "predictions.json").exists() else None
    pc = subprocess.run(["git", "log", "--diff-filter=A", "--format=%h", "--", pred], cwd=here, capture_output=True, text=True).stdout.split() if pred else []
    if not pc:
        print("note: predictions.json is missing or uncommitted; commit your expectations first if you want them pre-registered")
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    if a.agent == "claude":
        cmd = [a.claude, "-p", PROMPT, "--model", a.model or "claude-opus-5-5", "--setting-sources", "project", "--strict-mcp-config",
               "--allowedTools", TOOLS, "--output-format", "stream-json", "--verbose"]
    else:
        home = codex_home()
        env["CODEX_HOME"] = str(home)
        cmd = ["codex", "exec", "--json", "--skip-git-repo-check", "-s", "workspace-write", "-C", str(room)] + (["-m", a.model] if a.model else []) + [PROMPT]
    with open(run / "transcript.jsonl", "w", encoding="utf-8") as out, open(run / "stderr.txt", "w", encoding="utf-8") as err:
        # below-normal priority keeps the desktop responsive; run ONE room at a time on a GPU that also drives a display
        # (three concurrent rooms on a 16 GB card triggered a driver reset on 2026-10-18)
        if os.name == "nt":
            prio = {"creationflags": subprocess.BELOW_NORMAL_PRIORITY_CLASS}
        else:
            prio = {"preexec_fn": lambda: os.nice(10)}
        rc = subprocess.run(cmd, cwd=room, stdout=out, stderr=err, env=env, stdin=subprocess.DEVNULL, **prio).returncode
    if a.agent == "codex":
        shutil.rmtree(env["CODEX_HOME"], ignore_errors=True)
    meta = json.loads((run / "manifest.json").read_text(encoding="utf-8")) if (run / "manifest.json").exists() else {}
    meta["launch"] = {"agent": a.agent, "model": a.model or ("claude-opus-5-5" if a.agent == "claude" else "codex default"),
                      "flags": [c for c in cmd if c != PROMPT][1:], "exit_code": rc}
    if pc:
        meta["predictions_commit"] = pc[-1]
    (run / "manifest.json").write_text(json.dumps(meta, indent=1), encoding="utf-8")
    print(f"{a.agent} exited with {rc}; transcript in {run / 'transcript.jsonl'}")


if __name__ == "__main__":
    main()
