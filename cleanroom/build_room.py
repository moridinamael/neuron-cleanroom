"""Build a sealed clean room for a blind study of one neuron.

The room gets an allow-listed slice of the bonsai-interp toolchain at a pinned commit, the corpus
and scan, links to the model weights and Python environment, a neutral tool README, a brief, and
permission rules that deny the web and reads of the interp repo and Claude's memory. It never
gets the interp graph, probes, findings or reports.

  python -m cleanroom.build_room --interp ../bonsai-interp --ref main --neuron 14/2222 \
      --out ../rooms/L14_N2222 --run runs/2026-11-01_bonsai1_L14_N2222 [--hints none|methods]

Writes the room (its own git repo, first commit = the sealed state) and, outside the room,
<run>/manifest.json with the interp commit, file hashes, hint mode and seal rules.
"""
import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ALLOW = [
    "bonsai_interp/__init__.py", "bonsai_interp/model.py", "bonsai_interp/explore.py",
    "bonsai_interp/inverse/__init__.py", "bonsai_interp/inverse/problem.py", "bonsai_interp/inverse/solvers.py",
    "bonsai_interp/inverse/neuron.py", "bonsai_interp/inverse/linear.py",
    "bonsai_interp/probe/__init__.py", "bonsai_interp/probe/workspace.py", "bonsai_interp/probe/forward.py",
    "bonsai_interp/probe/textinv.py", "bonsai_interp/probe/run.py", "bonsai_interp/probe/induce.py",
    "bonsai_interp/probe/neighbors.py", "bonsai_interp/probe/quick.py", "bonsai_interp/probe/bands.py",
]
DATA = ["corpus.npz", "scan_bonsai1.npz"]
NEURON_REF = re.compile(r"\b(\d{1,2})/(\d{2,5})\b")  # neuron examples like 9/3688 in docstrings
MODEL_NAMES = {"bonsai1": ("Bonsai-8B (1-bit)", "Bonsai-8B-unpacked")}


def git(repo, *a, binary=False):
    return subprocess.run(["git", "-C", str(repo), *a], capture_output=True, check=True, text=not binary, encoding=None if binary else "utf-8").stdout


def slash(p: Path):
    """Claude Code permission-rule path form: //c/Users/... on Windows, //abs/path on POSIX."""
    s = p.resolve().as_posix()
    return "//" + (s[0].lower() + s[2:] if re.match(r"^[A-Za-z]:", s) else s.lstrip("/"))


def link(src: Path, dst: Path):
    if os.name == "nt":
        subprocess.run(["cmd", "/c", "mklink", "/J", str(dst), str(src)], check=True, capture_output=True)
    else:
        dst.symlink_to(src, target_is_directory=src.is_dir())


def scrub(text, L, n):
    """Replace example neuron references in docstrings so none points at the target or at a studied neuron."""
    return "".join(NEURON_REF.sub("12/345", ln) if re.search(r"-m |--neuron|--units|python ", ln) else ln
                   for ln in text.splitlines(keepends=True))


def build(a):
    interp, out = Path(a.interp).resolve(), Path(a.out).resolve()
    if out.exists():
        sys.exit(f"{out} exists; pick a new room folder")
    L, n = map(int, a.neuron.split("/"))
    commit = git(interp, "rev-parse", a.ref).strip()
    out.mkdir(parents=True)
    hashes = {}
    for f in ALLOW:
        src = git(interp, "show", f"{commit}:{f}")
        dst = out / f
        dst.parent.mkdir(parents=True, exist_ok=True)
        body = scrub(src, L, n)
        dst.write_text(body, encoding="utf-8")
        hashes[f] = hashlib.sha256(body.encode()).hexdigest()[:16]
    # data: hard links when possible (same volume), else copies
    (out / "data").mkdir()
    for f in DATA:
        s = Path(a.data) / f
        try:
            os.link(s, out / "data" / f)
        except OSError:
            shutil.copy2(s, out / "data" / f)
    (out / "models").mkdir()
    link(Path(a.models) / MODEL_NAMES[a.model][1], out / "models" / MODEL_NAMES[a.model][1])
    link(Path(a.venv), out / ".venv")
    if a.env and Path(a.env).exists():
        shutil.copy2(a.env, out / ".env")
    (out / "probes").mkdir()
    # docs
    readme = (HERE / "templates" / "README_TOOLS.md").read_text(encoding="utf-8")
    if a.hints == "none":
        readme = re.sub(r"<!-- HINTS:methods -->.*?<!-- /HINTS -->\n", "", readme, flags=re.S)
    else:
        readme = readme.replace("<!-- HINTS:methods -->\n", "").replace("<!-- /HINTS -->\n", "")
    (out / "README.md").write_text(readme, encoding="utf-8")
    brief = (HERE / "templates" / "BRIEF.md").read_text(encoding="utf-8").format(
        model_name=MODEL_NAMES[a.model][0], L=L, n=n, gmoo_budget=a.gmoo_budget, hours=a.hours)
    (out / "BRIEF.md").write_text(brief, encoding="utf-8")
    # the seal
    home = Path.home()
    deny = ["WebFetch", "WebSearch",
            f"Read({slash(interp)}/**)", f"Read({slash(home / '.claude')}/**)",
            f"Bash(*{interp.name}*)", "Bash(*.claude/projects*)", "Bash(*.claude\\projects*)"]
    if os.name == "nt":
        deny.append(f"Read({slash(home / 'AppData')}/**)")
    deny += [f"Read({slash(Path(p))}/**)" for p in a.deny_read]
    (out / ".claude").mkdir()
    (out / ".claude" / "settings.json").write_text(json.dumps(
        {"permissions": {"allow": ["Bash", "Read", "Edit", "Write", "Glob", "Grep", "Agent", "NotebookEdit"], "deny": deny}}, indent=2))
    (out / ".gitignore").write_text(".env\n.venv\nmodels/\ndata/*.npz\n__pycache__/\n")
    # leak check before sealing
    forbidden = [w.lower() for w in a.forbid]
    hits = [(p.relative_to(out).as_posix(), w) for p in out.rglob("*") if p.is_file() and p.suffix in (".py", ".md", ".json")
            and ".venv" not in p.parts and "models" not in p.parts
            for w in forbidden if w in p.read_text(encoding="utf-8", errors="ignore").lower()]
    if hits:
        for lk in [out / ".venv", *(out / "models").iterdir()]:  # unlink weights/env links before deleting
            os.rmdir(lk) if os.name == "nt" else lk.unlink()
        shutil.rmtree(out, ignore_errors=True)
        sys.exit(f"forbidden words found in the room, not sealed: {hits[:10]}")
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=out, check=True)
    subprocess.run(["git", "add", "-A"], cwd=out, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "Clean room: toolchain, brief"], cwd=out, check=True)
    room_commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=out, capture_output=True, text=True).stdout.strip()
    run = Path(a.run).resolve()
    run.mkdir(parents=True, exist_ok=True)
    (run / "manifest.json").write_text(json.dumps({
        "neuron": f"{a.model}/L{L}/N{n}", "room": str(out), "room_initial_commit": room_commit,
        "interp_commit": commit, "interp_ref": a.ref, "files": hashes, "hints": a.hints,
        "gmoo_budget": a.gmoo_budget, "hours": a.hours, "deny": deny, "forbid_checked": a.forbid}, indent=1), encoding="utf-8")
    shutil.copy2(out / "BRIEF.md", run / "BRIEF.md")
    print(f"room sealed at {out} (commit {room_commit[:7]}), interp {commit[:7]}, hints={a.hints}; manifest in {run}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--interp", required=True, help="path to a bonsai-interp checkout")
    ap.add_argument("--ref", default="main", help="git ref of bonsai-interp to take the toolchain from")
    ap.add_argument("--neuron", required=True, help="L/n")
    ap.add_argument("--model", default="bonsai1")
    ap.add_argument("--out", required=True, help="new folder for the room (outside any repo)")
    ap.add_argument("--run", required=True, help="run record folder in this repo")
    ap.add_argument("--data", help="folder with corpus.npz and scan_bonsai1.npz (default <interp>/data)")
    ap.add_argument("--models", help="folder with the model weights (default <interp>/models)")
    ap.add_argument("--venv", help="Python environment to link (default <interp>/.venv)")
    ap.add_argument("--env", help=".env with the globalMOO key (default <interp>/.env)")
    ap.add_argument("--hints", choices=["none", "methods"], default="none")
    ap.add_argument("--gmoo-budget", type=int, default=1)
    ap.add_argument("--hours", type=float, default=3)
    ap.add_argument("--deny-read", nargs="*", default=[], help="extra folders the agent must not read")
    ap.add_argument("--forbid", nargs="*", default=[], help="words that must not appear anywhere in the room, e.g. key words of the existing label (not the target id: the brief names it)")
    a = ap.parse_args()
    interp = Path(a.interp)
    a.data, a.models = a.data or interp / "data", a.models or interp / "models"
    a.venv, a.env = a.venv or interp / ".venv", a.env or interp / ".env"
    build(a)


if __name__ == "__main__":
    main()
