# DRAW-Paired provisional cohort (256 retained pairs)

> Provisional: exact source spans and deletions still require human approval.

| Model | Method | RSR | CAR | FDA | Unsupported/additions |
|---|---|---:|---:|---:|---:|
| GPT-OSS 20B | Grounded self-review | 62.5 | 83.6 | 73.0 | 44.3 |
| GPT-OSS 20B | DeGro | 66.4 | 90.2 | 78.3 | 37.5 |
| GPT-OSS 120B | Grounded self-review | 52.3 | 84.4 | 68.4 | 52.3 |
| GPT-OSS 120B | DeGro | 64.1 | 91.8 | 77.9 | 38.8 |
| Nemotron Nano 30B | Grounded self-review | 34.8 | 85.5 | 60.2 | 62.8 |
| Nemotron Nano 30B | DeGro | 46.9 | 93.0 | 69.9 | 45.5 |

## Paired primary comparison

- GPT-OSS 20B: +5.3 FDA points (95% CI [+2.0, +8.8]); McNemar p=0.00359635, Holm p=0.00359635.
- GPT-OSS 120B: +9.6 FDA points (95% CI [+6.1, +13.3]); McNemar p=8.41232e-08, Holm p=2.52369e-07.
- Nemotron Nano 30B: +9.8 FDA points (95% CI [+5.1, +14.5]); McNemar p=2.87757e-05, Holm p=5.75515e-05.
