# Nemotron 3 Nano 30B additional MIRA comparison

Post-hoc model addition; frozen prompts/data, temperature 1.0, API think=medium. Same API request does not establish equal internal reasoning budgets.

## Fixed 120-pair set (960/960 valid records)

| Method | RSR (%) | CAR (%) | FDA (%) | ORR (%) | UR (%) |
|---|---:|---:|---:|---:|---:|
| self_review | 76.7 | 92.5 | 84.6 | 7.5 | 25.8 |
| grounded_self_review | 80.8 | 98.3 | 89.6 | 1.7 | 3.0 |
| nonunique | 50.8 | 96.7 | 73.8 | 3.3 | 24.7 |
| nonunique_grounding | 81.7 | 100.0 | 90.8 | 0.0 | 1.0 |

DeGro minus grounded self-review: +1.25 FDA points, pair-cluster 95% CI [-2.5, 5.0], exact McNemar p=0.663624; 12 versus 9 discordances. Statistically inconclusive.

## Secondary cumulative 300-pair set (2400/2400 valid records)

FDA: 89.5% grounded self-review versus 90.3% DeGro (+0.83 points, 95% CI [-1.5, 3.3], exact McNemar p=0.590053; 30 versus 25 discordances). Includes development data; does not replace fixed-set inference.

Sensitivity Holm across all three fixed-set model tests: GPT-OSS 20B p=0.100205, GPT-OSS 120B p=0.040593, Nemotron p=0.663624. Original two-GPT-OSS test family is separately retained.

All expected keys and stored scores were independently verified against frozen data. Raw retries retain first valid responses, not score-selected samples. Frozen input and output SHA-256 values appear in the run manifest.
