"""Export a finished room's contributions into bonsai-interp, so every blind run fills in the map.

  python -m cleanroom.export --run runs/<run> --interp ../bonsai-interp [--no-commit]

1. Reads the room (before it is removed) and its git history.
2. Keeps a contribution only if its pre-registration (.tests.json) was committed in the room
   strictly BEFORE its results; anything else is reported and skipped.
3. On a new branch cleanroom/<run> from origin/main, commits in two steps, so the order is kept:
   first the tests files plus our predictions for the run, then the results, the edges, and one
   'replicate' contribution per pole that carries the agent's final label and verdict.
   Results gain a "provenance" field pointing at the room commits in this repository's bundle.
4. Validates the contributions, checks the commit order, pushes the branch and opens a PR with
   contribution files and run evidence only (no derived graph files). With --merge it also merges
   the PR with a merge commit and pushes a fold commit on main (validate --strict as a circuit breaker).
"""
import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path


def git(repo, *a):
    return subprocess.run(["git", "-C", str(repo), *a], capture_output=True, text=True, encoding="utf-8", check=True).stdout


def first_commit(repo, path):
    out = git(repo, "log", "--diff-filter=A", "--format=%H", "--", path).split()
    return out[-1] if out else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--interp", required=True)
    ap.add_argument("--no-commit", action="store_true")
    ap.add_argument("--repo", default="moridinamael/bonsai-interp")
    ap.add_argument("--merge", action="store_true", help="also merge the PR (merge commit) and push a fold commit on main")
    a = ap.parse_args()
    run, interp = Path(a.run).resolve(), Path(a.interp).resolve()
    man = json.loads((run / "manifest.json").read_text(encoding="utf-8"))
    room = Path(man.get("repo") or man["room"])
    committed = lambda d: git(d, "log", "--format=%H", "--", "graph/contributions").strip() if (d / ".git").exists() else ""
    if not committed(room):  # e.g. Codex made its own nested checkout to commit in
        nested = [d for d in Path(man["room"]).iterdir() if d.is_dir() and (d / ".git").exists() and committed(d)]
        if nested:
            room = max(nested, key=lambda d: len(list((d / "graph" / "contributions").rglob("*.json"))))
            print(f"using the nested repository {room.name}/ for contributions and their commit order")
    handle = man.get("handle", "cleanroom-claude")
    cdir = room / "graph" / "contributions"
    results = [p for p in cdir.glob("*/*/*.json") if not p.name.endswith(".tests.json")] if cdir.exists() else []
    take, skipped, tests_files = [], [], set()
    for p in sorted(results):
        rel = p.relative_to(room).as_posix()
        c = json.loads(p.read_text(encoding="utf-8"))
        rc = first_commit(room, rel)
        ok, prov = rc is not None, {"cleanroom_run": run.name, "room_results_commit": rc}
        for t in c.get("tests", []):
            tc = first_commit(room, t["tests_file"])
            if not (tc and rc and tc != rc and git(room, "merge-base", "--is-ancestor", tc, rc) == ""):
                ok = False
            prov["room_tests_commit"] = tc
        if ok:
            take.append((p, rel, c, prov))
            tests_files.update(t["tests_file"] for t in c.get("tests", []))
        else:
            skipped.append(rel)
    branch = f"cleanroom/{run.name}"
    if not a.no_commit:
        git(interp, "fetch", "-q", "origin")
        git(interp, "checkout", "-q", "-b", branch, "origin/main")
    # 1) tests files + predictions
    pred_dst = interp / "runs" / "cleanroom" / run.name
    pred_dst.mkdir(parents=True, exist_ok=True)
    if (run / "predictions.json").exists():
        shutil.copy2(run / "predictions.json", pred_dst / "predictions.json")
    for tf in sorted(tests_files):
        dst = interp / tf
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(room / tf, dst)
    if not a.no_commit:
        git(interp, "add", "graph/contributions", str(pred_dst.relative_to(interp)))
        git(interp, "commit", "-q", "-m", f"Clean-room run {run.name}: pre-registered tests (verified first in the room) and our predictions")
    # 2) results, edges, replicate summaries
    for p, rel, c, prov in take:
        c["provenance"] = {**prov, "bundle": f"neuron-cleanroom/{run.relative_to(run.parents[1]).as_posix()}/room.bundle"}
        if not c.get("methods"):  # rooms built before the methods block: fill it from the room and the launch record
            launch = man.get("launch", {})
            files = {q.name for q in (room / "probes").rglob("*") if q.is_file()} if (room / "probes").exists() else set()
            seen = {"look"} | {"quick-test"} | ({"bands"} if list((room / "data").glob("bands_*.npz")) else set())                 | ({"bank-solo"} if "solo.json" in files else set()) | ({"held-out"} if "holdout.json" in files else set())                 | ({"inverse-de"} if "invert_de.json" in files else set()) | ({"inverse-gmoo"} if "invert_gmoo.json" in files else set())                 | ({"induce"} if "induce.json" in files else set()) | ({"neighbors"} if "neighbors.json" in files else set())                 | ({"step-out"} if c.get("kind") == "map" or "feeds" in " ".join(c.get("roles", [])) else set())
            c["methods"] = {"agent": f"{launch.get('agent', 'claude')} {launch.get('model', '')}".strip() + " (blind room)",
                            "screens": sorted(seen | {"blind-room"}), "harness": "neuron-cleanroom", "inferred_at_export": True}
        dst = interp / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text(json.dumps(c, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
    summ = json.loads((run / "summary.json").read_text(encoding="utf-8")) if (run / "summary.json").exists() else {}
    L, n = man["neuron"].split("/")[1:]
    for pole, key in (("+", "pole_plus"), ("-", "pole_minus")):
        b = summ.get(key)
        if not b:
            continue
        nid = f"bonsai1/{L}/{n}{pole}"
        folder = f"{L}_{n}_{'pos' if pole == '+' else 'neg'}"
        cid = f"core-{run.name.lower().replace('_', '-')}-{'pos' if pole == '+' else 'neg'}-blind"
        launch = man.get("launch", {})
        rc = {"id": cid, "kind": "replicate", "neuron": nid, "contributor": handle, "created": git(room, "log", "-1", "--format=%cI").strip(),
              "methods": {"agent": f"{launch.get('agent', 'claude')} {launch.get('model', '')}".strip() + " (blind room)",
                          "screens": ["blind-room"], "harness": "neuron-cleanroom"},
              "label": b["label"], "verdict": b["verdict"], "confidence": b["confidence"],
              "evidence": [f"runs/cleanroom/{run.name}/REPORT.md"],
              "tests": [{"protocol": "cleanroom@1", "tests_file": f"runs/cleanroom/{run.name}/predictions.json",
                         "prereg_commit": f"neuron-cleanroom@{man.get('predictions_commit', '?')}", "outcome": "recorded",
                         "result_file": f"runs/cleanroom/{run.name}/REPORT.md"}]}
        d = interp / "graph" / "contributions" / "bonsai1" / folder
        d.mkdir(parents=True, exist_ok=True)
        (d / f"{cid}.json").write_text(json.dumps(rc, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
    for f in ("REPORT.md", "summary.json", "audit.json", "scored.json"):
        if (run / f).exists():
            shutil.copy2(run / f, pred_dst / f)
    py = interp / ".venv" / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
    v = subprocess.run([str(py), "-m", "bonsai_interp.graph.validate"], cwd=interp, capture_output=True, text=True, encoding="utf-8")
    print(v.stdout[-1500:])
    if v.returncode != 0:
        sys.exit("validate failed: fix before committing the results")
    print(f"exported {len(take)} contributions; skipped {len(skipped)} whose order could not be verified: {skipped}")
    if a.no_commit:
        return
    git(interp, "add", "graph/contributions", str(pred_dst.relative_to(interp)))
    git(interp, "commit", "-q", "-m", f"Clean-room run {run.name}: results, edges and blind verdicts ({len(take)} contributions)")
    c = subprocess.run([str(py), "-m", "bonsai_interp.graph.check_prereg", "--base", "origin/main"], cwd=interp, capture_output=True, text=True, encoding="utf-8")
    print(c.stdout[-800:])
    if c.returncode != 0:
        sys.exit(f"check_prereg failed on branch {branch}; nothing pushed")
    git(interp, "push", "-q", "-u", "origin", branch)
    summ_line = " · ".join(f"{k}: {v.get('verdict')}" for k, v in summ.items() if isinstance(v, dict) and "verdict" in v)
    body = "\n".join([
        f"Blind clean-room run `{run.name}` ({man.get('launch', {}).get('agent', 'claude')}), exported by `cleanroom.export`.", "",
        f"- Contributions: {len(take)} (pre-registration order verified in the room's git history; provenance in each results file)",
        f"- Blind verdicts: {summ_line}",
        f"- Audit: see runs/cleanroom/{run.name}/audit.json",
        "- Methods: blind-room (+ screens listed per contribution)", "",
        "Contribution files and run evidence only; no derived graph files."])
    pr = subprocess.run(["gh", "pr", "create", "--repo", a.repo, "--head", branch, "--base", "main",
                         "--title", f"replicate: blind run {run.name}", "--body", body], cwd=interp, capture_output=True, text=True, encoding="utf-8")
    print(pr.stdout.strip() or pr.stderr.strip())
    if a.merge:
        url = pr.stdout.strip()
        subprocess.run(["gh", "pr", "merge", url, "--merge", "--repo", a.repo], cwd=interp, check=True)
        git(interp, "checkout", "-q", "main")
        git(interp, "pull", "-q", "origin", "main")
        subprocess.run([str(py), "-m", "bonsai_interp.graph.fold"], cwd=interp, check=True)
        strict = subprocess.run([str(py), "-m", "bonsai_interp.graph.validate", "--strict"], cwd=interp, capture_output=True, text=True, encoding="utf-8")
        if strict.returncode != 0:
            sys.exit("validate --strict failed after the fold; NOT pushing the fold commit (circuit breaker)\n" + strict.stdout[-800:])
        git(interp, "add", "graph/neurons", "graph/edges.json", "graph/index.json")
        git(interp, "commit", "-q", "-m", f"fold after {url.rsplit('/', 1)[-1] if url else run.name}")
        git(interp, "push", "-q", "origin", "main")
        print("merged, folded on main and pushed")


if __name__ == "__main__":
    main()
