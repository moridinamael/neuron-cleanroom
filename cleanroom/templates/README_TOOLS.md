# Neuron probing toolchain (Bonsai-8B, 1-bit)

Tools for finding out what one MLP neuron of Bonsai-8B does. The model is a 1-bit
quantization-aware-trained Qwen3-8B variant, 36 layers, 12,288 SwiGLU channels per layer.

A **neuron** is one SwiGLU channel: `silu(gate) * up` at layer L, index n. It has two
**poles**: the positive side and the negative side. They are often unrelated jobs, so study
each separately. **L12/N345+** means layer 12, neuron 345, positive pole.

Activations are usually given as a **fraction of the pole's corpus maximum**. The corpus is
8M tokens of mixed web text, code and multilingual text, and 1.0 is the strongest token in it.

Run everything with the local environment:

```
.venv/Scripts/python -m <module> ...
```

Set `PYTHONIOENCODING=utf-8` so non-Latin text prints. The GPU fits **one model at a
time**, so run model-loading jobs one after another. Loading takes about 30–60 s.

## Data

- `data/corpus.npz`: `tokens`, shape (windows, 1024), the scanned corpus.
- `data/scan_bonsai1.npz`: top-32 activations per pole for every neuron, with window and
  position. `explore.py` reads it.

## Tools

### Forward: what text activates it

- `python -m bonsai_interp.explore --model bonsai1 --neuron L/n [--pole +|-] [--k 12]`
  - Top corpus examples. The peak token is marked ⟦like this⟧.
  - Also shows the sign regime of each example (gate × up).
- `python -m bonsai_interp.probe.run forward L/n +`
  - Writes `probes/bonsai1_L{L}_N{n}_pos/forward.json` with the top examples of both poles.
  - Writes `bank_request.json`, which asks for a sentence bank. You write that bank (see below).
- `bonsai_interp.probe.bands`: the full activation distribution, not just the top 32.
  - `python -m bonsai_interp.probe.bands scan --units L/n[,L/n...] --windows 6000 --tag X` records every
    token's activation for those neurons over 6,000 windows (about 6M tokens).
  - `bands.sample(tag, L, n, pole, k, bands=[(lo, hi), ...])` draws random contexts from
    activation bands (fractions of the pole's corpus max).
  - `bands.load_bands(tag)["L{L}_N{n}"]` returns the raw per-token array.

### Testing text you write

- `textinv.TextEvaluator(model, tok, rec, L, n, pole_max, opp_max, sign)`
  - Call it on a list of strings. It returns, per string, `act` (this pole) and `opp`
    (the other pole), each as a fraction of its corpus max, plus `peak_token`.
  - Each text is read after neutral preambles. Activation is taken only on the text's own
    tokens, because the first positions of a sequence are damped.
  - `bonsai_interp.probe.run.setup(ws)` builds one from `forward.json`.
- `python -m bonsai_interp.probe.quick L/n +` runs a pre-registered quick test from
  `probes/<id>/quick_tests.json`:

  ```
  {"neighbours": [{"unit": "L12/N345", "pole": "+", "label": "...", "fire": [8 sentences], "quiet": [8 sentences]}]}
  ```

  - A label holds if at least 5 of 8 "fire" sentences reach 0.3 and at most 1 "quiet" sentence does.
  - It also prints the vocabulary tokens that drive the neuron directly and, if the layer is
    above 0, the earlier neurons that feed it. Pass `with_feeders=False` to skip the feeders.
  - It works for any neuron, so you can use it on neighbours too.

### Sentence bank, dose-response and held-out tests

`python -m bonsai_interp.probe.run solo L/n +` needs `bank.json` in the probe folder:

```
{"label": {"+": "...", "-": "..."},
 "hypotheses": {"rel_pos": "label A", "rel_h2": "label B", ...},   # optional, competing labels
 "concept_tokens": [" word", ...], "opposite_tokens": [" word", ...], # used by induce
 "sentences": [{"text": ..., "rel_pos": 0..1, "rel_neg": 0..1, "branch": ..., "kind": "on|near|spelling|opposite|unrelated|corpus|top",
                "rel_h2": 0..1, ...}]}
```

- Relevance ratings (0–1) give how well each sentence matches each label.
- The stage reports, for each hypothesis, the Spearman correlation and AUROC between rating and
  activation, plus leaks (fires off-concept) and silent on-concept sentences.
- If `holdout.json` exists, it also scores that pre-registered held-out test:

  ```
  {"hypothesis": "rel_pos", "sentences": [{"text": ..., "predict": "fire|quiet"}]}
  ```

### Inverse: from a target activation back to text

`python -m bonsai_interp.probe.run invert L/n + --solver de|gmoo [--goals a,b]` searches over passages
of 3 sentences drawn from the bank. Each sentence is placed by a (concept, strength)
coordinate. The goals are defined in `textinv.GOALS`:

- **Levels:** hit 25 / 50 / 75% of max.
- **max:** the strongest text in the bank's span.
- **leak:** fire with nothing related to the label present.
- **offshoot:** fire without the refined sense.
- **silent_on_concept:** the concept is present but the neuron stays quiet.
- **near_miss_ceiling:** the strongest text that is at most related.

There are two solvers:

- `de`: SciPy differential evolution. Local, robust, about 600 evaluations per goal.
- `gmoo`: globalMOO, a learned inverse model. It trains once, then answers each goal in a few
  evaluations. It needs the key in `.env` and makes remote calls. **Use at most one globalMOO
  model in this whole study.** Choose the problem carefully.

You can also build your own `InverseProblem`s (`bonsai_interp/inverse/problem.py`) and use
`bonsai_interp/inverse/solvers.py`: `differential_evolution`, `dual_annealing`, `least_squares`,
`lbfgs`, `GmooInverse`.

### Induce: what the neuron does to the model's output

`python -m bonsai_interp.probe.run induce L/n +` adds c × (pole max) to the neuron during neutral
prompts. It reports:

- the tokens the neuron's output direction promotes and suppresses directly
- p(concept_tokens) and p(opposite_tokens) as c varies
- KL from the unsteered model
- the tokens that gain probability
- greedy generations at several c

### Circuits

`python -m bonsai_interp.probe.neighbors L/n +` needs `neighbors_request.json`:

```
{"branches": {"name": ["text", {"text": ..., "find": "substring of the token to read"}]},
 "flip": {"alone": "text where it fires", "flipped": "same text after context that silences it", "find": "token substring"}}
```

It reports:

- **Upstream:** attribution, then zeroing each candidate alone. The share of the activation
  lost is that neuron's input weight.
- **Disambiguators:** for the flip pair, which upstream units push it down.
- **Downstream:** which later neurons change when this one is zeroed.

Lower-level pieces:

- `bonsai_interp.inverse.neuron.NeuronSite`: one corpus position. Gives attribution and masked runs.
- `bonsai_interp.inverse.linear`: weights-only views (`token_weights`, `virtual_weights`).
- `bonsai_interp.model.load("bonsai1")` returns `(model, tok, rec)`. `rec` is a `NeuronRecorder`:
  - set `rec.mode = "act"` and `rec.layers = {L}` to record
  - use `rec.interventions = {L: fn}` to edit activations
  - set `rec.stop_at = L` to stop the forward pass early (raises `StopForward`)

### Recording labels in the shared format

`bonsai_interp.graph.play` writes tests and results in the format of the public map.

| Command | What it does |
|---|---|
| `play look --neuron bonsai1/L12/N345+` | top corpus examples |
| `play new interpret --neuron … --handle …` | writes `graph/contributions/…/<id>.tests.json`. Fill it in, then commit it alone |
| `play run <tests file>` | refuses uncommitted or edited test files; writes `<id>.json` with per-sentence results. Commit it separately |
| `play step --neuron … --k 4` | the strongest feeders of a pole (attribution, then single-unit zeroing on its top examples) |
| `play edge --from … --to … --weight … --handle …` | records a measured edge |

## Good practice

- Write predictions and test sentences down, and `git commit` them, **before** you run them.
<!-- HINTS:methods -->
- Look beyond the top examples: weak and middling activations, and how often each kind of
  trigger occurs in the corpus.
- Prefer tests that could embarrass your label: near misses, the concept without its usual
  words, the usual words without the concept, other languages, competing hypotheses.
<!-- /HINTS -->
