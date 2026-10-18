# Brief

**Target:** Bonsai-8B (1-bit), MLP neuron **layer 9, index 3688**, both poles (L9/N3688+ and L9/N3688−).

**Question:** What does this neuron do? Is each pole monosemantic, meaning it does one
interpretable job? If not, what are its jobs?

No prior work on this neuron is available to you, and none should be sought. Work only inside
this folder with the toolchain in `README.md`. Do not use the web. Do not read files outside
this folder.

## What to do

- Investigate both poles with the forward, inverse, induce and circuit tools. Use your own
  judgement about which tools and how much of each.
- Form labels, then **try hard to break them**. Look at weak and middling activations, not
  only the top examples. Write test sentences that could embarrass your label. Pit competing
  hypotheses against each other.
- **Pre-register:** write test sets and predictions to files and `git commit` them before
  running them. Note the commit hashes in your report.
- You may use sub-agents, for example to label examples blind or to write test sentences.
- **Budget:** at most **one** globalMOO model in total. SciPy solvers are unlimited. Aim to
  finish within about 3 hours of wall-clock time.

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
