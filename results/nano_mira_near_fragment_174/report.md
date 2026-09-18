# Nano on the MIRA near-fragment extension

This is an exploratory extension and is not merged into the paper's MIRA-300 main result.

## Cohort construction

All 210 source instances from `geometry_coordinates` (60) and `laplace_grid`
(150) in the frozen MIRA-Math release were considered before model inference.
The paired construction retained every instance for which removing the canonical
hint leaves a satisfiable, target-ambiguous formalization and restoring it uniquely
determines the gold target.

- Geometry: 60/60 retained.
- Laplace: 114/150 retained.
- Laplace exclusions: 36/150; the target was already determinate without the
  withheld fact, so these instances cannot test repair versus abstention.
- Final extension: 174 pairs / 348 cases.

For geometry, the formal target is squared Euclidean distance. Because Euclidean
distance is nonnegative, its square is uniqueness-equivalent while remaining in
the supported SMT fragment. This adapter choice is a limitation and must be
reported if the cohort is published.

## Run configuration

Model: `nemotron-3-nano:30b`; thinking enabled; temperature 1.0; unchanged
MIRA-300 prompt and scorer; four methods; first valid response retained without
outcome-based retries. All 1,392 expected records completed.

| Method | FDA | RSR | CAR | UR |
|---|---:|---:|---:|---:|
| Self-review | 57.8 | 25.3 | 90.2 | 43.6 |
| Grounded self-review | 58.0 | 17.8 | 98.3 | 16.2 |
| Non-uniqueness | 54.9 | 23.0 | 86.8 | 46.7 |
| DeGro | **62.6** | **27.0** | **98.3** | **9.6** |

Rates are percentages. UR is unsupported additions among all proposed additions.

DeGro exceeds grounded self-review by 4.60 FDA points (pair-cluster 95% CI
[1.15, 8.05]); 27 versus 11 discordant cases favor DeGro; exact paired
two-sided p=.0139 (Holm p=.0277 across the two available decision comparisons).
This inference is exploratory because the families were added after inspection of
the original MIRA-300 experiment.

## Family analysis

| Family | Method | FDA | RSR | CAR |
|---|---|---:|---:|---:|
| Geometry (60 pairs) | Grounded self-review | 72.5 | 50.0 | 95.0 |
|  | DeGro | **85.8** | **73.3** | **98.3** |
| Laplace (114 pairs) | Grounded self-review | 50.4 | 0.9 | **100.0** |
|  | DeGro | 50.4 | 2.6 | 98.2 |

Geometry drives the aggregate gain: DeGro improves FDA by 13.33 points, with
24 versus eight discordances (exact p=.0070). On Laplace, both methods obtain the
same 50.44 FDA; each has three uniquely correct cases (p=1.0). The near-chance
Laplace FDA is caused by failure to restore the missing boundary value, not failure
to abstain on underspecified sources.

## Audit

- Recomputed all 1,392 stored scores: zero changes.
- Verified every omission contains its exact gold source span once and every
  underspecified mate omits it.
- Verified all 174 IDs are disjoint from the original MIRA-300.
- Verified all 174 base formalizations are target-ambiguous and all gold actions
  pass the scorer.
- Test suite: 59 passed.

Artifacts:

- Dataset: `data/paired/mira_near_fragment_174.jsonl`
- Dataset manifest: `data/paired/mira_near_fragment_174.manifest.json`
- Complete records: `results/nano_mira_near_fragment_174/nano_mira_near_fragment_174_complete.jsonl`
- Full statistical output: `results/nano_mira_near_fragment_174/analysis.json`
