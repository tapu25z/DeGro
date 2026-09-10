# ALG514 natural-error analysis

Status: GPT-OSS 120B label proposals; all 503 rows remain pending human verification.

## Cohort

- Official ALG514 release: 514 problems across five original folds.
- Joint verifier coverage: 503/514 (97.86%).
- Frozen annotation cohort: 503 problems.
- Excluded before annotation: 6 solver-level `NOT_SUPPORTED`, 1 model-declared unsupported, and 4 inconsistent formalizations.
- The annotation unit is one original problem and its shared joint-target formalization.

## Proposed semantic labels

| Label | Count | Cohort rate | Share of proposed errors |
|---|---:|---:|---:|
| `CORRECT` | 470 | 93.44% | — |
| `WRONG_TARGET` | 12 | 2.39% | 36.36% |
| `WRONG_CONSTRAINT` | 9 | 1.79% | 27.27% |
| `MISSING_CONSTRAINT` | 6 | 1.19% | 18.18% |
| `EXTRA_CONSTRAINT` | 4 | 0.80% | 12.12% |
| `WRONG_DOMAIN` | 2 | 0.40% | 6.06% |

The proposed semantic-error rate is 33/503 (6.56%). Target-critical underformalization is 6/503 (1.19%), so omitted constraints are not the dominant natural error in this cohort. `WRONG_TARGET` is the largest proposed class.

GPT-OSS 120B returned 502 `HIGH`-confidence and 1 `LOW`-confidence proposal. Confidence is model-reported and is not calibration evidence. Of 503 successful calls, 501 used reasoning `none`; two retry cases used `low`, with this difference retained in the raw audit records.

## Outcome metrics and evaluator correction

The released ALG514 `solutions` field contains values for every equation unknown, even when the natural-language question requests only one of them. It also contains some values rounded to three decimal places. Consequently, the original exact-cardinality comparison incorrectly marked many valid single-target outputs as wrong.

For diagnostic reporting, ALG514-compatible matching treats generated target values as a multiset subset of the released solution vector and uses tolerance `1e-3`:

| Method | Legacy correct | ALG514-compatible correct | Accuracy |
|---|---:|---:|---:|
| Structured solver | 396/514 | 484/514 | 94.16% |
| DeGro | 396/514 | 485/514 | 94.36% |

DeGro triggered on 15 ambiguous cases, accepted two grounded changes, and made one additional case determinate, a gain of 1/514 (0.19 percentage points). The resolved case was `alg514/2121`, where the question explicitly supplied the missing equality condition. The other accepted change did not resolve ambiguity.

## Main validity finding

- 18 cases were numerically compatible with the released solution vector but received a semantic-error proposal. Outcome accuracy therefore hides target, constraint, and domain defects.
- Four cases received `CORRECT` proposals but remained verifier-ambiguous under ALG514-compatible scoring. These are `alg514/353`, `alg514/1035`, `alg514/5454`, and `alg514/6779` and should be reviewed first. Inequality questions that ask for a threshold and ratio constraints involving division are recurrent sources of this disagreement.
- The numerical and semantic views measure different properties and should be reported side by side, not collapsed into one accuracy number.

## Fold check

| Fold | Cohort size | Proposed errors | Error rate |
|---|---:|---:|---:|
| 0 | 99 | 5 | 5.05% |
| 1 | 100 | 9 | 9.00% |
| 2 | 99 | 7 | 7.07% |
| 3 | 100 | 9 | 9.00% |
| 4 | 105 | 3 | 2.86% |

The observed error rate varies by fold, but this table is descriptive; no confirmatory fold-difference claim is made.

## Reporting rule

Until the review queue is verified, describe these as “GPT-OSS 120B label proposals” or “AI-assisted annotations pending human verification.” Do not describe them as completed human annotations.
