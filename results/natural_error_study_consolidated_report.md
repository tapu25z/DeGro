# Consolidated human-verified natural-error study

Date: 2026-09-11

DRAW-1K is excluded from this consolidated study. Its files remain as development artifacts but its labels and outcomes are not used below.

## Study scope

| Dataset | Input | Frozen cohort | Coverage | Human verification |
|---|---:|---:|---:|---|
| MATH-500 | 500 | 292 | 58.40% | Two reviewers, 292/292 accepted |
| ALG514 | 514 | 503 | 97.86% | Two reviewers, 503/503 accepted |
| **Total** | **1,014** | **795** | **78.40%** | **795/795 reviewed** |

Each case is a naturally generated GPT-OSS 20B formalization; no error was injected. Both final label sets were fully inspected by two human reviewers. Separate pre-discussion human label files were not recorded, so the process is full two-person verification of AI-assisted labels, not independent blinded double annotation; no human Cohen's kappa is reported.

## Descriptive label totals

| Label | MATH-500 | ALG514 | Combined count |
|---|---:|---:|---:|
| `CORRECT` | 158 | 477 | 635 |
| `WRONG_TARGET` | 69 | 11 | 80 |
| `WRONG_CONSTRAINT` | 32 | 7 | 39 |
| `MISSING_CONSTRAINT` | 24 | 8 | 32 |
| `EXTRA_CONSTRAINT` | 8 | 0 | 8 |
| `WRONG_DOMAIN` | 1 | 0 | 1 |
| **Total** | **292** | **503** | **795** |

The combined counts are descriptive only. A pooled 160/795 error rate should not be presented as a population prevalence estimate because MATH-500 has strong solver-fragment selection (58.4% coverage), whereas ALG514 has 97.86% coverage and a narrower algebra distribution.

## MATH-500 results

### Cohort

- Input: 500 problems.
- Frozen cohort: 292 conclusive, solver-supported formalizations.
- Excluded: 65 model-declared unsupported, 112 solver-unsupported, 9 inconsistent, 9 solver-unknown, and 13 call errors.
- Packet SHA-256: `a7f16240f80c9838a6823516760c6754f8787dc2ebb57626c710c804e352e063`.
- Final labels: Gemma 4 31B proposals, fully checked and accepted by two human reviewers.
- Verified-label SHA-256: `4e1bbe0b9eaefdefe4569ec10fdd42daf8f1131d17dfbc410d0faed0b430ad38`.

### Human-verified taxonomy

| Label | Count | Rate |
|---|---:|---:|
| `CORRECT` | 158 | 54.11% |
| `WRONG_TARGET` | 69 | 23.63% |
| `WRONG_CONSTRAINT` | 32 | 10.96% |
| `MISSING_CONSTRAINT` | 24 | 8.22% |
| `EXTRA_CONSTRAINT` | 8 | 2.74% |
| `WRONG_DOMAIN` | 1 | 0.34% |

The natural semantic-error rate is 134/292 (45.89%). The target-critical underformalization subset contains 24/292 cases (8.22%). This prevalence is conditional on the supported cohort and must not be generalized to all MATH-500 problems without the coverage qualification.

### Detection and repair

| Metric | Result | Rate | Wilson 95% CI |
|---|---:|---:|---:|
| Recall on target-critical missing constraints | 21/24 | 87.50% | [69.00%, 95.66%] |
| Detector precision | 21/121 | 17.36% | [11.64%, 25.08%] |
| End-to-end successful repair of missing constraints | 1/24 | 4.17% | [0.74%, 20.24%] |
| Repair success conditional on detection | 1/21 | 4.76% | [0.85%, 22.67%] |
| False ambiguity outside missing-constraint subset | 100/268 | 37.31% | [31.74%, 43.24%] |
| False repair outside missing-constraint subset | 21/268 | 7.84% | [5.18%, 11.68%] |
| Preservation of correct controls | 126/158 | 79.75% | [72.81%, 85.27%] |

The detector has high recall but low precision. Most naturally ambiguous formalizations are wrong-target, wrong-constraint, or otherwise outside the target-critical missing-constraint subset. Detection therefore does not imply repairability.

### End-to-end accuracy

| Method | Correct | Accuracy | Wilson 95% CI |
|---|---:|---:|---:|
| Structured Solver | 144/292 | 49.32% | [43.63%, 55.02%] |
| DeGro | 157/292 | 53.77% | [48.04%, 59.40%] |

- Absolute gain: **4.45 percentage points**.
- Discordant pairs: 16 favor DeGro; 3 favor Structured Solver.
- Exact paired McNemar: **p = 0.00443**.

This is a statistically detectable end-to-end gain on the frozen supported cohort, but not evidence that DeGro reliably repairs target-critical omissions: only 1/24 such cases ended in successful repair.

## ALG514 results

### Cohort

- Input: all 514 problems across five official folds.
- Excluded: 6 solver-unsupported, 1 model-declared unsupported, and 4 inconsistent formalizations.
- Frozen cohort: 503/514 (97.86%).
- Packet SHA-256: `35b41922795b3ca86d3b9e2b21dfe33fb58ad68bbd2b02d5aa030fa5b9d020fa`.
- GPT-OSS 120B labelled all cases and adjudicated 22 semantic/verifier disagreements; two human reviewers then accepted all 503 labels.
- Verified-label SHA-256: `72217047ff8d41b4a3766e504325821bd07230d7b6dc7636475294ab8e5ffecd`.

### Human-verified taxonomy

| Label | Count | Rate | Share of errors |
|---|---:|---:|---:|
| `CORRECT` | 477 | 94.83% | — |
| `WRONG_TARGET` | 11 | 2.19% | 42.31% |
| `MISSING_CONSTRAINT` | 8 | 1.59% | 30.77% |
| `WRONG_CONSTRAINT` | 7 | 1.39% | 26.92% |

- Natural semantic-error rate: 26/503 = **5.17%**, Wilson 95% CI [3.55%, 7.47%].
- Target-critical underformalization: 8/503 = **1.59%**, Wilson 95% CI [0.81%, 3.11%].
- `WRONG_TARGET` is the largest error category.

### Numerical outcomes

ALG514-compatible scoring treats generated targets as a multiset subset of the released all-unknown solution vector and uses tolerance `1e-3` for rounded values.

| Method | Correct | Accuracy |
|---|---:|---:|
| Structured Solver | 484/514 | 94.16% |
| DeGro | 485/514 | 94.36% |

- Ambiguity triggers: 15.
- Accepted DeGro changes: 2.
- Ambiguous cases resolved: 1.
- Gain: **0.19 percentage points**.
- Nine cases produce numerically compatible answers despite a human-verified semantic error.
- Two cases are semantically accepted but remain verifier-ambiguous under the numerical protocol.

The principal ALG514 finding is that answer accuracy can hide target and constraint errors. DeGro's one-case improvement should be described as exploratory.

## Cross-dataset conclusions

1. Natural-error prevalence is dataset-dependent: 45.89% on the supported MATH-500 cohort versus 5.17% on ALG514.
2. Wrong-target errors dominate both cohorts: 69/134 MATH-500 errors and 11/26 ALG514 errors.
3. DeGro detects most target-critical omissions on MATH-500 (87.5% recall), but successful repair is rare (4.17%).
4. DeGro improves MATH-500 cohort accuracy by 4.45 points with paired p=0.00443, whereas ALG514 improves by 0.19 points.
5. Nine answer-compatible semantic errors on ALG514 demonstrate why answer-only evaluation is insufficient.
6. Coverage must accompany every prevalence claim, especially for MATH-500's 58.4% supported subset.

## Paper-ready reporting

The paper may report MATH-500 and ALG514 as human-verified, AI-assisted natural-error studies. It should state that two reviewers checked every final label, while avoiding claims of independent double annotation or human inter-annotator agreement. DRAW-1K is excluded from the study and all aggregate claims.
