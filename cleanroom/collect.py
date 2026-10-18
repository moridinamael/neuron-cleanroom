"""Collect a finished room into its run record: the report, the summary, and a git bundle of the
room's full history (so every pre-registration commit the agent made can be checked).

  python -m cleanroom.collect --run runs/<run>
"""
import argparse
import json
import shutil
import subprocess
from pathlib import Path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    a = ap.parse_args()
    run = Path(a.run).resolve()
    room = Path(json.loads((run / "manifest.json").read_text(encoding="utf-8"))["room"]).expanduser()
    for f in ("REPORT.md", "summary.json"):
        if (room / f).exists():
            shutil.copy2(room / f, run / f)
        else:
            print(f"missing {f} in the room")
    subprocess.run(["git", "bundle", "create", str(run / "room.bundle"), "--all"], cwd=room, check=True, capture_output=True)
    log = subprocess.run(["git", "log", "--format=%h %ad %s", "--date=iso"], cwd=room, capture_output=True, text=True).stdout
    (run / "room_git_log.txt").write_text(log, encoding="utf-8")
    from cleanroom.export import redact
    redact(run)  # no local paths or user name in committed evidence (run the audit before collecting)
    print(f"collected into {run}:\n{log}")


if __name__ == "__main__":
    main()
