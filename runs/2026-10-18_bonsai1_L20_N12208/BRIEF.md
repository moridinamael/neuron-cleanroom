# Brief

**Target:** Bonsai-8B (1-bit), MLP neuron **layer 20, index 12208**, both poles (L20/N12208+ and L20/N12208−).

**Question:** What does this neuron do? Is each pole monosemantic, meaning it does one
interpretable job? If not, what are its jobs?

No prior work on this neuron is available to you, and none should be sought. Work only inside
this folder with the toolchain in `README.md`. Do not use the web. Do not read files outside
this folder.

## What to do

- Investigate both poles with the forward, inverse, induce and circuit tools. Use your own
  judgement about which tools and how much of each.
- Form labels, then **try hard to break them**.
- **Pre-register:** write test sets and predictions to files and `git commit` them before
  running them. Note the commit hashes in your report.
- You may use sub-agents, for example to label examples blind or to write test sentences.
- **Budget:** at most **1** globalMOO model(s) in total. SciPy solvers are
  unlimited. Aim to finish within about 3 hours of wall-clock time.
- The model weights, corpus and scan are already in place (see README). Don't download anything.

## Record your labels as contributions

Your tested labels will be added to a shared public map, so record them in its format. Any other
analysis can use whatever tools you like.

- **For each pole's final label**, and for any earlier label you want on record, run:

  ```
  python -m bonsai_interp.graph.play new interpret --neuron bonsai1/L20/N12208<+|-> --handle cleanroom-claude
  ```

  Fill in the file it writes: the label, 8 sentences that should fire, 8 near misses, and
  optionally `short`, `unit_kind` and `confidence`. Commit that file **on its own**. Then run
  `python -m bonsai_interp.graph.play run <that file>` and commit the results in a **separate,
  later** commit. A failed label is worth recording too.
- **Map the immediate neighbourhood.** For each pole, list its strongest feeders:

  ```
  python -m bonsai_interp.graph.play step --neuron bonsai1/L20/N12208<+|-> --k 4
  ```

  Take the two with the largest drop. For each one:
  1. Label it from its top examples (`play look`).
  2. Test that label the same way (`play new interpret`, commit, `play run`, commit). Add
     `"roles": ["feeds bonsai1/L20/N12208<pole>"]` to its tests file.
  3. Record the edge with
     `python -m bonsai_interp.graph.play edge --from <feeder id> --to <this pole's id> --weight <drop> --handle cleanroom-claude`.

  Keep this light: one quick test per feeder.

## Deliverables

Write both files in this folder, then commit everything.

**`REPORT.md`** should cover:

- the final label for each pole, and the labels you rejected along the way, with the evidence
  that rejected them
- the key evidence for the final labels (numbers, example sentences, test results)
- a monosemanticity verdict per pole: monosemantic, one main job with offshoots, several jobs,
  or unclear. Explain why, and give your confidence.
- what you would test next, and what you are least sure about

**`summary.json`** has this shape:

```
{"pole_plus": {"label": ..., "verdict": ..., "confidence": 0..1}, "pole_minus": {...},
 "rejected_labels": [...], "key_tests": [{"name", "prediction", "result", "commit"}]}
```
