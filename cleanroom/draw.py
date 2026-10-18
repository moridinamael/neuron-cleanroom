"""Draw a random neuron for a blind run, reproducibly, and record the draw before anyone looks.

  python -m cleanroom.draw --seed 20261020 --interp ../bonsai-interp [--layers 6-24] [--agent claude]
    -> runs/<date>_bonsai1_L{L}_N{n}/selection.json  (commit it before looking at the neuron)

The first neuron whose poles are both absent from the interp graph is used, whatever it looks like.
"""
import argparse
import datetime as dt
import json
import random
from pathlib import Path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, required=True)
    ap.add_argument("--interp", required=True)
    ap.add_argument("--layers", default="6-24")
    ap.add_argument("--agent", default="claude")
    ap.add_argument("--qc", action="store_true", help="draw a QC sample: a held, not-yet-replicated pole from the graph")
    a = ap.parse_args()
    lo, hi = map(int, a.layers.split("-"))
    idx = json.loads((Path(a.interp) / "graph" / "index.json").read_text(encoding="utf-8"))["neurons"]
    known = set(idx)
    rng = random.Random(a.seed)
    if a.qc:  # QC sample: a held, not-yet-replicated pole, chosen at random so the quick tier stays honest
        pool = sorted(k for k, v in idx.items() if v["status"] == "held" and not v.get("replicated"))
        pick = rng.choice(pool)
        L, n = int(pick.split("/")[1][1:]), int(pick.split("/")[2][1:-1])
    else:
        while True:
            L, n = rng.randint(lo, hi), rng.randrange(12288)
            if f"bonsai1/L{L}/N{n}+" not in known and f"bonsai1/L{L}/N{n}-" not in known:
                break
    run = Path(__file__).resolve().parents[1] / "runs" / f"{dt.date.today().isoformat()}_bonsai1_L{L}_N{n}"
    run.mkdir(parents=True, exist_ok=True)
    (run / "selection.json").write_text(json.dumps({
        "drawn": dt.datetime.now().isoformat(timespec="seconds"), "seed": a.seed, "layers": a.layers, "agent": a.agent,
        "mode": "qc-sample" if a.qc else "new",
        "rule": ("random.Random(seed).choice over held, not-yet-replicated poles in the graph (QC sample)" if a.qc else
                 "random.Random(seed): layer uniform in the range, index uniform in 0..12287; redraw only if a pole is already in the graph. "
                 "The first such draw is used whatever it looks like."), "neuron": f"bonsai1/L{L}/N{n}"}, indent=1), encoding="utf-8")
    print(f"{L}/{n} {run}")


if __name__ == "__main__":
    main()
