# DRAW-Paired provisional 300

> Provisional: exact source spans and deletions still require human approval.

| Model | Method | RSR | CAR | FDA | Unsupported/additions |
|---|---|---:|---:|---:|---:|
| GPT-OSS 20B | Grounded self-review | 62.3 | 83.0 | 72.7 | 44.5 |
| GPT-OSS 20B | DeGro | 59.7 | 89.7 | 74.7 | 44.1 |
| GPT-OSS 120B | Grounded self-review | 53.0 | 84.3 | 68.7 | 50.9 |
| GPT-OSS 120B | DeGro | 59.0 | 91.7 | 75.3 | 43.1 |
| Nemotron Nano 30B | Grounded self-review | 33.0 | 86.3 | 59.7 | 64.6 |
| Nemotron Nano 30B | DeGro | 40.7 | 92.0 | 66.3 | 52.5 |

## Paired primary comparison

- GPT-OSS 20B: +2.0 FDA points (95% CI [-1.5, +5.5]); McNemar p=0.30709, Holm p=0.30709.
- GPT-OSS 120B: +6.7 FDA points (95% CI [+3.2, +10.2]); McNemar p=0.000198237, Holm p=0.000594711.
- Nemotron Nano 30B: +6.7 FDA points (95% CI [+2.3, +11.0]); McNemar p=0.00195373, Holm p=0.00390746.
