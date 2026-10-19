# Context: what is already known about bonsai1/L9/N3688+ (guided circuit trace)

This is a **guided** run. You are given the map and our expectations so that you can spend your time on the open
question instead of rediscovering the basics. Treat everything below as claims to test, and pre-register every test
before you score it.

## The neuron

`bonsai1/L9/N3688+`: layer 9, neuron 3688, the positive pole of the SwiGLU product `silu(gate) * up`.

- **Current label (status "probed"):** "A lexical detector peaking on the psychological word 'nerve', with weaker
  reliable branches for 'strong' and hit/hurt words."
- **Corpus card:** among its top 32 corpus peaks, the peak token is `' nerve'` 9 times and `' strong'` 7 times.
  Density is sparse (about 0.12% of tokens reach 0.1 of the max).
- **The − pole of the same neuron** is a separate, held unit: somatosensory and nociceptive physiology (pain, touch,
  receptors, fibres).

## What has been tested

1. **Dual-sense hypothesis, rejected.** We asked whether it fires for words with both a physical and a psychological
   sense. Excluding 'strong', 0 of 24 such sentences fired at ≥ 0.3. Its two strongest triggers prefer *opposite*
   senses: **physical 'strong'** (0.48 physical, 0.07 psychological) and **psychological 'nerve'**.
2. **"Psychological 'nerve' only", refined QC, failed** (AUROC 0.875). The near miss "The ulnar nerve runs along
   the inside of the elbow." fired **0.47**. The fire sentence "The goalkeeper held his nerve and saved the last
   penalty." fired only **0.08**. So it is not a clean psychological-sense detector either.
3. **Blind clean-room replication** of the neuron: an independent agent reached a lexical 'nerve' label with offshoots.

## The neighbourhood (from the graph; "drop" = share of this pole's activation lost when the source is zeroed)

| edge | kind | weight | the other pole's label (status) |
|---|---|---|---|
| L3/N6493+ → this | feeds | 0.73 | spelling "nerv/nerf" (held) |
| L8/N7756+ → this | feeds | 0.61 | the nerve concept, in Arabic (held) |
| L5/N5628− → this | feeds | 0.15 | nervous-system anatomy and neurological disease words (held) |
| L7/N1548− → this | feeds | 0.10 | the word 'vein(s)' in its literal sense (held) |
| L8/N3858+ → this | gates | −0.25 | pain (held) |
| this → L10/N6901+, L10/N5553−, L13/N3792+, L14/N9470+, L19/N2291+, L20/N5963− | reads | all ≤ 0.11 | mostly dense hubs |
| co-fires with L8/N7756+, L10/N2242+ (autonomic), L12/N3688+ (overwhelmed), L7/N9782+ (suspense), L7/N619+ (weak), L9/N1061+ (can't wait) | co-fires | 0.56-0.69 | |

These edges were all measured on **'nerve'** contexts. **Nothing is known about what feeds the 'strong' branch.**

## The open question

Why do 'nerve' (psychological) and 'strong' (physical) share this pole? Two explanations make different predictions:

- **Packing:** two unrelated features share one neuron. Prediction: the 'strong' branch has its **own feeders**,
  largely disjoint from the 'nerve' feeders above, and zeroing L3/N6493+ barely touches 'strong' activations.
  Downstream, the two branches are read by different units, or by no consistent unit.
- **Shared downstream use:** both feed one later computation, e.g. a resilience or strength-of-constitution feature.
  Prediction: the branches **converge on common readers** that respond to the neuron's output in both contexts,
  and the two senses' outputs push the residual stream in similar directions.

The 'ulnar nerve' result adds a third possibility to rule in or out: a **lexical 'nerve' detector whose strength is
set by context**, not by sense. If so, find out what context makes anatomical 'nerve' fire (0.47) while 'held his
nerve' does not (0.08).

## What we would like back

1. A pre-registered test of the 'strong' branch (8 + 8, `play new` / `play run`) and its **feeders** (`play step` on
   'strong' contexts), recorded with `play edge`.
2. A test of whether L3/N6493+ and L8/N7756+ matter for 'strong' (zero them on 'strong' contexts).
3. The **readers**: which downstream units respond to this pole's output in 'nerve' vs 'strong' contexts.
4. The ulnar-vs-goalkeeper contrast explained by a tested hypothesis (what makes the word fire it).
5. A verdict: packing / shared downstream use / context-weighted lexical 'nerve' / something else, with confidence.
   Draw the circuit you found (text is fine) in REPORT.md.
