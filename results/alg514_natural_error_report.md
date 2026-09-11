# ALG514 natural-error analysis

Status: fully human-verified, AI-assisted annotation. Two human reviewers inspected all 503 final labels and accepted 503/503 without changes.

## Cohort

- Official ALG514 release: 514 problems across five original folds.
- Joint verifier coverage: 503/514 (97.86%).
- Frozen annotation cohort: 503 problems.
- Excluded before annotation: 6 solver-level `NOT_SUPPORTED`, 1 model-declared unsupported, and 4 inconsistent formalizations.
- The annotation unit is one original problem and its shared joint-target formalization.

## Final human-verified semantic labels

| Label | Count | Cohort rate | Share of proposed errors |
|---|---:|---:|---:|
| `CORRECT` | 477 | 94.83% | — |
| `WRONG_TARGET` | 11 | 2.19% | 42.31% |
| `MISSING_CONSTRAINT` | 8 | 1.59% | 30.77% |
| `WRONG_CONSTRAINT` | 7 | 1.39% | 26.92% |

The human-verified semantic-error rate is 26/503 (5.17%). Target-critical underformalization is 8/503 (1.59%), so omitted constraints are not the dominant natural error in this cohort. `WRONG_TARGET` is the largest class.

GPT-OSS 120B first labelled all 503 cases, after which it adjudicated the 22 cases where semantic status and verifier-compatible numerical status disagreed. Eleven labels changed and eleven were retained. The final file contains 22 explicitly adjudicated rows and 481 initial proposals. Model-reported confidence is not calibration evidence.

Two human reviewers subsequently checked the complete 503-case label set and accepted every final label. Separate pre-discussion human label files were not recorded, so this is full two-person verification rather than an independent blinded double-annotation design; Cohen's kappa is therefore not reported.

## Outcome metrics and evaluator correction

The released ALG514 `solutions` field contains values for every equation unknown, even when the natural-language question requests only one of them. It also contains some values rounded to three decimal places. Consequently, the original exact-cardinality comparison incorrectly marked many valid single-target outputs as wrong.

For diagnostic reporting, ALG514-compatible matching treats generated target values as a multiset subset of the released solution vector and uses tolerance `1e-3`:

| Method | Legacy correct | ALG514-compatible correct | Accuracy |
|---|---:|---:|---:|
| Structured solver | 396/514 | 484/514 | 94.16% |
| DeGro | 396/514 | 485/514 | 94.36% |

DeGro triggered on 15 ambiguous cases, accepted two grounded changes, and made one additional case determinate, a gain of 1/514 (0.19 percentage points). The resolved case was `alg514/2121`, where the question explicitly supplied the missing equality condition. The other accepted change did not resolve ambiguity.

## Main validity finding

- Nine cases are numerically compatible with the released solution vector but retain a semantic-error decision. Outcome accuracy therefore hides target or constraint defects.
- Two cases retain a semantic `CORRECT` decision while remaining verifier-ambiguous under ALG514-compatible scoring. These disagreements are now explicit final AI decisions rather than unresolved records.
- The numerical and semantic views measure different properties and should be reported side by side, not collapsed into one accuracy number.

## Fold check

| Fold | Cohort size | Proposed errors | Error rate |
|---|---:|---:|---:|
| 0 | 99 | 4 | 4.04% |
| 1 | 100 | 9 | 9.00% |
| 2 | 99 | 4 | 4.04% |
| 3 | 100 | 6 | 6.00% |
| 4 | 105 | 3 | 2.86% |

The observed error rate varies by fold, but this table is descriptive; no confirmatory fold-difference claim is made.

## Reporting rule

Describe these as “AI-assisted labels fully verified by two human reviewers.” Do not describe the process as independent blinded double annotation, and do not report inter-annotator agreement because separate pre-discussion human label files were not recorded.
