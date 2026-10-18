# neuron-cleanroom

Blind replication of neuron interpretations. An AI agent is given a neuron, the toolchain and
the data, and **nothing else**. In particular, it gets no labels, results or notes from earlier
work. It is asked to find out what the neuron does, to try to break its own labels, and to
pre-register its tests by committing them first. We compare what it finds with the existing
interpretation.

The point is to test whether a published label comes from the neuron or from the path its
authors happened to take.

This repository holds the harness and the record of every run. The toolchain and the interp
graph live in [bonsai-interp](https://github.com/moridinamael/bonsai-interp). The harness takes
the toolchain from a **pinned commit** of that repo and never copies the graph, probes or
findings into a room.

## When to use a blind room

Blind rooms are the most expensive check in the survey: one to two GPU-hours per neuron. They are
**sampled QC**, not the default way to label. Quick missions colour in the map; a random sample of
held labels (about one in ten) gets a blind room, drawn with `cleanroom.draw --qc --seed <n>` so the
choice is reproducible and can't be cherry-picked. Use a blind room on purpose for a contested label,
a label about to be cited, or a circuit trace. Run one room at a time on a GPU that also drives a display.

## How a run works

1. **Build the room** with `cleanroom.build_room`. This creates a new folder with its own git
   repo, containing:
   - an allow-listed slice of `bonsai_interp`: forward, bands, text evaluation, quick tests,
     sentence bank, inverse solvers (SciPy and globalMOO), induce and neighbours
   - neuron examples in docstrings replaced by a dummy, `12/345`
   - the corpus and corpus scan (hard links)
   - links to the model weights and Python environment
   - a neutral tool README and a brief built from `cleanroom/templates/`
   - a `.claude/settings.json` seal that denies the web, reads of the interp repo and reads of
     Claude's memory and transcripts

   The build fails if any `--forbid` word appears in the room. The `--forbid` words are, for
   example, the existing label's key terms or the target id. `--hints none` (the default)
   leaves out method advice learned from earlier studies; `--hints methods` keeps it.
2. **Pre-register your expectations.** Write `runs/<run>/predictions.json` with probabilities
   and commit it before launching.
3. **Launch** with `cleanroom.launch`. This runs a headless Claude Code process in the room with
   no MCP servers, only project settings, and a fixed prompt. Every message and tool call is
   recorded to `runs/<run>/transcript.jsonl`.
4. **Audit** with `cleanroom.audit`. It flags every tool call that names a path outside the
   room, the interp repo, Claude's memory, or uses a web tool. Sub-agent calls are included.
5. **Collect** with `cleanroom.collect`. It copies the report and summary, and makes a git
   bundle of the room's full history so the agent's pre-registration commits can be checked.
6. **Score** your predictions in `runs/<run>/scored.json`, then remove the room with
   `cleanroom.remove_room`. This unlinks the weights and environment links before deleting.

```bash
python -m cleanroom.build_room --interp ../bonsai-interp --ref main --neuron 14/2222 \
    --out ../rooms/L14_N2222 --run runs/2026-11-01_bonsai1_L14_N2222 --forbid <known label words>
git add runs/2026-11-01_bonsai1_L14_N2222 && git commit -m "Pre-register expectations for L14/N2222"
python -m cleanroom.launch --room ../rooms/L14_N2222 --run runs/2026-11-01_bonsai1_L14_N2222
python -m cleanroom.audit --run runs/2026-11-01_bonsai1_L14_N2222
python -m cleanroom.collect --run runs/2026-11-01_bonsai1_L14_N2222
python -m cleanroom.remove_room ../rooms/L14_N2222
```

The harness needs Python 3.11+ (standard library only), git, and the
[Claude Code CLI](https://docs.claude.com/en/docs/claude-code). It also needs a bonsai-interp
checkout with its data (`scripts/fetch_data.sh`), models and environment.

**Platforms.** Windows is the reference platform, and macOS and Linux work too. The
platform-specific parts sit behind `os.name` checks, so each platform keeps its own behaviour:

| | Windows | macOS and Linux |
|---|---|---|
| Weight and environment links (build, remove) | junctions | symlinks |
| Read-only git object files on remove | cleared before deleting | no handler needed |
| Codex config | `[windows] sandbox = "unelevated"` | none; Codex's own sandbox (Seatbelt on macOS) |
| Agent process priority | below normal | `nice 10` |

On a Mac the room runs the toolchain on Apple's MPS backend. Export `BONSAI_DEVICE=mps` before
`cleanroom.launch`, so that a room which cannot reach the GPU stops at once instead of running on
the CPU. bonsai-interp's README, under "Running on a Mac", has the requirements.

## What "blind" does and does not mean here

What the room contains and what the agent is told:

- **Blind to results.** The room contains no labels, probes, findings or reports for any
  neuron. The brief tells the agent that no prior work is available and that none should be
  sought.
- **Not blind to methods.** The toolchain carries the method's choices: neutral preambles, the
  8 + 8 quick-test threshold and the inverse goal battery. With `--hints methods`, it also
  carries advice learned from earlier studies.

How that is enforced and checked:

- **Enforced by permission rules, verified by audit.** The seal blocks the web and reads of the
  interp repo and Claude's memory. It is not an OS sandbox: a shell command could still reach
  outside the room. The audit of the full transcript is what makes the claim checkable, and it
  is published with every run.

Limits on independence:

- **Same model family.** If the agent and the original investigator are both Claude, they share
  priors. Runs with other models, or human investigators, are welcome.

## Runs

| Run | Neuron | Hints | Outcome |
|---|---|---|---|
| [2026-10-17](runs/2026-10-17_bonsai1_L9_N3688/) | bonsai1/L9/N3688 ("nerve") | methods | Audit clean (51 calls, 0 flagged). The agent found the 'nerve', 'strong' and violent-harm branches and called the + pole "several jobs". The − pole is somatosensory physiology. 6 of 8 pre-registered predictions held. The room was built by hand before `build_room.py` existed; see its `manifest.json`. |
| [2026-10-18](runs/2026-10-18_bonsai1_L12_N5397/) | bonsai1/L12/N5397 (random draw, seed 20261018) | none | Audit clean (77 calls; 2 uses of its own scratchpad to hide a blind-test key). Found a window-start artifact in the scan behind our failed + label. The + pole peaks on row-ending line breaks in long hex/byte dumps; the − pole is four number/code sub-jobs with separate feeders. Verdict: several jobs for both poles. 7 of 8 predictions held. |

## Licence

Code: MIT. Run records (reports, transcripts, audits) are released under CC-BY-4.0, like the
interp graph.
