# Exploratory MIRA-360 with Geometry60

This report mechanically combines the original MIRA-300 records with all 60
validated `geometry_coordinates` pairs. The extension was designed after the
original outcomes were available, so MIRA-360 is exploratory rather than an
independent confirmatory evaluation.

## Geometry60 alone

| Model | Method | FDA | RSR | CAR | UR |
|---|---|---:|---:|---:|---:|
| GPT-OSS 20B | Grounded self-review | 94.2 | 90.0 | 98.3 | 3.6 |
|  | DeGro | **96.7** | **93.3** | **100.0** | **0.0** |
| GPT-OSS 120B | Grounded self-review | 95.8 | 95.0 | 96.7 | 5.0 |
|  | DeGro | **98.3** | **96.7** | **100.0** | **3.3** |
| Nano 30B | Grounded self-review | 72.5 | 50.0 | 95.0 | 16.7 |
|  | DeGro | **85.8** | **73.3** | **98.3** | **2.2** |

## Combined MIRA-360

| Model | Method | FDA | RSR | CAR | UR |
|---|---|---:|---:|---:|---:|
| GPT-OSS 20B | Self-review | 90.6 | 93.1 | 88.1 | 14.5 |
|  | Grounded self-review | 91.7 | 94.7 | 88.6 | 11.2 |
|  | Non-uniqueness | 92.6 | 88.1 | 97.2 | 7.9 |
|  | DeGro | **96.3** | 93.3 | 99.2 | 2.9 |
| GPT-OSS 120B | Self-review | 78.6 | 99.4 | 57.8 | 29.9 |
|  | Grounded self-review | 89.6 | 96.7 | 82.5 | 15.5 |
|  | Non-uniqueness | 92.4 | 98.6 | 86.1 | 13.4 |
|  | DeGro | **96.1** | 97.8 | 94.4 | 6.4 |
| Nano 30B | Self-review | 83.9 | 76.1 | 91.7 | 25.5 |
|  | Grounded self-review | 86.7 | 75.0 | 98.3 | 4.6 |
|  | Non-uniqueness | 72.9 | 53.9 | 91.9 | 27.3 |
|  | DeGro | **89.6** | 79.4 | 99.7 | 1.0 |

Rates are percentages. UR is unsupported additions among all additions.

## DeGro versus grounded self-review

| Model | FDA delta | Pair-cluster 95% CI | Discordances (DeGro / grounded) | Exact p | Cross-model Holm p |
|---|---:|---:|---:|---:|---:|
| GPT-OSS 20B | +4.58 | [+2.08, +7.08] | 56 / 23 | .000264 | .000527 |
| GPT-OSS 120B | +6.53 | [+4.31, +8.75] | 61 / 14 | 3.81e-8 | 1.14e-7 |
| Nano 30B | +2.92 | [+0.42, +5.42] | 54 / 33 | .0314 | .0314 |

All three comparisons remain significant after Holm adjustment across the three
model-specific DeGro-versus-grounded comparisons. This does not remove the
post-hoc status of the Geometry60 extension.

## Protocol and audit

- Geometry60 contains every geometry instance in the frozen MIRA-Math release;
  no outcome-based filtering was applied.
- The formal target is squared Euclidean distance, which is uniqueness-equivalent
  to nonnegative Euclidean distance but is an adapter-specific representation.
- GPT-OSS 20B and 120B each produced 480/480 valid Geometry60 records with the
  same prompt hash, temperature 1.0, and medium reasoning setting as MIRA-300.
- Every one of the 960 new GPT-OSS scores was independently recomputed with zero
  changes. Each MIRA-360 file has 2,880 unique records.
- Nano Geometry60 comes from its previously completed near-fragment run. The old
  Nano main records use the literal API request `think="medium"`, while the new
  records use `think=true`; the public Nano renderer treats both as thinking-on.
- Test suite: 59 passed.

MIRA-360 should not silently replace MIRA-300. If reported, the paper must state
the extension timing, target adapter, and exploratory status.
