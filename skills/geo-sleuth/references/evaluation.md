# Evaluate changes without leaking the answer

A passing unit test proves a code contract, not improved photo geolocation.
Use this protocol before claiming a better solve rate or reduced false precision.
Keep answers and case-specific tuning out of the installed skill and region packs.

## Separate three kinds of result

1. **Offline regression:** a reproducible bug or CLI contract with controlled inputs.
2. **Known-answer replay:** a disclosed example, useful for numerical regressions.
3. **Blind localization:** a fresh solver sees the photo and declared hints, not the answer,
   README case narrative, case-specific scripts, or evaluator workspace.

Never count a known-answer replay as a blind success. The public README images
may be resized/cropped display assets, not equivalent to the original input.

## Paired experiment

- Use consented/public-landmark images with documented reuse rights. Keep private
  photos and location keys local. No person identification or private-home targeting.
- A separate evaluator holds `answers.json`; solvers receive only neutral case IDs,
  image bytes and predeclared hints. Separate work directories prevent cache/log leakage.
- Record the original input SHA-256, dimensions, crop/resize/orientation operations,
  metadata policy, source rights, expected accuracy and provenance of ground truth.
- Run baseline and changed skill with the same model/provider, reasoning settings,
  tool access, credentials, hints and time/cost limits. Record the exact skill commit.
  Alternate run order; repeat cases with fresh contexts to expose variance.
- Stratify at least by region, urban/rural, text/no text, skyline/no skyline, street-view
  coverage, season mismatch, image quality and independent-source availability.
  Choose sample size from the effect size and uncertainty you need; a few showcase
  cases are not enough for a general accuracy claim.
- Freeze each prediction and complete run trace before opening the key. Retain the
  hash/timestamp in a separate evaluator log. Hashes identify bytes, but do not prove
  the key was hidden or that freezing happened before disclosure.
- Report location error, candidate recall before/after every filter, Recall@K for
  ranking stages, searched/unsearched extent, time, tool calls, cost, model downloads,
  failed/partial routes, and abstentions. Compare paired outcomes and uncertainty,
  not just overall wins. Review the first stage where the true location disappeared.

## Scorer

`evaluate.py` takes two JSON arrays. Keep the truth array outside solver workspaces.

Truth example (artificial coordinates for format demonstration only):

```json
[{"case_id":"demo","lat":0,"lon":0}]
```

Prediction, or explicit abstention:

```json
[{"case_id":"demo","lat":0,"lon":0,"radius_m":100}]
```

```json
[{"case_id":"demo","abstain":true}]
```

Run from an evaluator-only directory:

```bash
uv run /absolute/path/to/geo-sleuth/scripts/evaluate.py --truth answers.json --predictions frozen.json --out metrics.json
```

The scorer rejects duplicate/unknown case IDs, invalid/nonfinite coordinates,
contradictory abstentions and negative/nonfinite radii. Missing predictions stay
in all-case denominators and are listed separately from explicit abstentions.
It reports all-case accuracy and predicted-only accuracy at 25/100/1000 m and
25/200/750/2500 km, mean/median error, prediction coverage, empirical radius
coverage, median claimed radius and failed precision claims of ≤100 m.
Input SHA-256 values bind metrics to exact arrays. Distance is spherical with
mean Earth radius 6371008.8 m, not survey-grade ellipsoidal geodesy.

Empirical radius coverage is not a calibrated probability: a huge radius can
cover the truth while being useless. Read it alongside radius size, exact error,
coverage, and stratified results. No stated confidence level is inferred.
The scorer does not verify photo provenance, blinding, completeness of traces,
run cost or runtime. Those remain evaluator duties.

## Acceptance before shipping a capability

- Reproduce its motivating failure and show the changed behavior with real output.
- Retain the old route/switch when adding a model or fitted degree of freedom.
- Check unmodified, independent cases; don't tune and test on the same photo set.
- Do not promote a model, provider or prompt merely because its README claims a
  high score on a different dataset. Measure candidate recall and verified solves
  on the relevant workload under equal budgets.
