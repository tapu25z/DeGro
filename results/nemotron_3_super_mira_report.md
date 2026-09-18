# Nemotron 3 Super additional MIRA comparison

Post-hoc model addition on the same frozen data/prompts and four methods. Temperature 1.0; API think=medium (not a guarantee of equal internal reasoning budgets).

## Fixed 120-pair set (960/960 valid records)

| Method | RSR (%) | CAR (%) | FDA (%) | ORR (%) | UR (%) |
|---|---:|---:|---:|---:|---:|
| Self-review | 79.2 | 96.7 | 87.9 | 3.3 | 14.4 |
| Grounded self-review | 74.2 | 98.3 | 86.3 | 1.7 | 4.3 |
| Determinacy-guided | 85.0 | 97.5 | 91.3 | 2.5 | 6.4 |
| DeGro | 84.2 | 97.5 | 90.8 | 2.5 | 4.7 |

DeGro minus grounded self-review: +4.58 FDA points, pair-cluster 95% CI [0.0, 9.2], exact McNemar p=0.080143 (22 versus 11 discordances). Statistically inconclusive on the fixed set. Verdict-only repair scores highest (91.25% versus 90.83% DeGro).

## Secondary cumulative 300-pair set (2400/2400 valid records)

FDA: 84.17% grounded self-review versus 89.83% DeGro (+5.67 points, 95% CI [2.5, 8.7], exact McNemar p=0.000509; 63 versus 29 discordances). Verdict-only FDA: 91.5%. Includes development data and does not replace fixed-set inference.

Sensitivity Holm over all four fixed-set model tests: GPT-OSS 20B p=0.150307, GPT-OSS 120B p=0.054124, Nano p=0.663624, Super p=0.160287. None is below .05. Original two-GPT-OSS family is retained separately.

All expected unique keys, frozen input hashes, request configurations, and independently recomputed scores passed verification. Raw files contain exactly 2400 successful records and zero error records. Percentages use half-up rounding. Provider-reported tag digest: da11955bb451.
