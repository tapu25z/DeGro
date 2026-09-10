# Decision-baseline result (GPT-OSS 20B)

## Run integrity

- Dataset: the same 100 held-out pairs (200 cases) used by the six-method run.
- Added methods: `grounded_self_review` and `minimal_witness_grounding`.
- New calls: 400/400 successful; no failed records in the finalized file.
- Combined analysis: 1,600 successful records, all from `gpt-oss:20b`.

## Main results

| Method | RSR | CAR | FDA | Unsupported additions |
|---|---:|---:|---:|---:|
| SelfReview | 92.0% | 84.0% | 88.0% | 18.6% |
| GroundedSelfReview | 93.0% | 90.0% | 91.5% | 10.6% |
| MinimalWitness | 93.0% | 93.0% | 93.0% | 13.1% |
| MinimalWitness+Grounding | 97.0% | 99.0% | 98.0% | 2.0% |
| NonUnique+Grounding | 97.0% | 100.0% | 98.5% | 1.0% |
| TargetCheck | 97.0% | 98.0% | 97.5% | 3.0% |

RSR is measured on omission cases, CAR on underspecified cases, and FDA on all
cases. Unsupported is the fraction of attempted additions that fail the grounded
gold-repair criterion.

## Paired comparisons

- MinimalWitness+Grounding versus NonUnique+Grounding on FDA: -0.5 percentage
  points; discordant cases 3 versus 4; exact McNemar p=1.0.
- The two methods tie on RSR (97% versus 97%; exact McNemar p=1.0).
- MinimalWitness+Grounding trails by one CAR case (99% versus 100%; exact
  McNemar p=1.0).
- GroundedSelfReview versus SelfReview improves FDA by 3.5 points, but this is
  not significant after Holm correction (adjusted p=0.592).
- NonUnique+Grounding exceeds GroundedSelfReview by 7 FDA points (discordant
  cases 17 versus 3; unadjusted exact McNemar p=0.00258). This shows that the
  grounding instruction alone does not explain the full result.
- Adding grounding to MinimalWitness improves FDA by 5 points. The unadjusted
  p-value is 0.0309, but the decision-family Holm-adjusted p-value is 0.0927.

## Decision

Minimal witnesses show no incremental value beyond the non-uniqueness verdict
plus grounding on this benchmark. Do not retain the claim that witnesses are
better. The next benchmark should test *when* witnesses help by including several
source-supported omitted facts per problem while making only one omitted fact
target-critical.

These two baselines were added after inspecting the original six-method result,
so their comparisons must be described as a decision-stage follow-up rather than
as part of the original preregistration.
