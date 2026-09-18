# DeGro source-coverage refinement: Nano 30B and GPT-OSS 120B

## Status

Complete. The experiment contains 320/320 development responses and 800/800 synthetic-test responses. Verification recomputed every score, checked every expected key, configuration and prompt digest, and confirmed that each finalized record is the first valid response for its key.

## Candidate and selection

One candidate prompt was designed from errors on the 80-pair development split. It asks the model to:

- compare every factual condition in the source against the current formalization using algebraic equivalence;
- consider conditions among non-target variables that can determine the target indirectly;
- distinguish ambiguity of the current formalization from insufficiency of the original source;
- treat the provided variable declarations and bounds as already enforced.

The candidate prompt receives no label, gold target, missing constraint or pair identifier. Temperature 1.0, medium reasoning and the original output schema and deterministic scorer are retained. No alternative candidate was selected using test outcomes.

## Evaluation data

The 300 solver-compatible MIRA pairs were already exhausted by pilot, development and confirmatory splits. The new evaluation is therefore a generated synthetic stress test, not new MIRA and not an external benchmark. It contains 100 pairs: 25 each from linear separation, graph path sums, Chinese-remainder reconstruction and rank-deficient linear systems. All 200 gold actions independently pass the released scorer. Every source string is unique and none exactly matches the original 300-pair source strings; shared templates still limit independence.

The original and refined DeGro prompts were rerun concurrently on both models. The primary comparison is FDA with a 10,000-sample pair-cluster bootstrap interval and exact paired McNemar test. Holm adjustment covers the two model tests.

## Results

| Model | Prompt | RSR | CAR | FDA | ORR | UR |
|---|---|---:|---:|---:|---:|---:|
| Nemotron Nano 30B | Original DeGro | 52.0% | 99.0% | 75.5% | 1.0% | 1/53 = 1.9% |
| Nemotron Nano 30B | Source coverage | 90.0% | 100.0% | **95.0%** | 0.0% | 8/98 = 8.2% |
| GPT-OSS 120B | Original DeGro | 99.0% | 98.0% | 98.5% | 2.0% | 3/102 = 2.9% |
| GPT-OSS 120B | Source coverage | 100.0% | 99.0% | **99.5%** | 1.0% | 1/101 = 1.0% |

For Nano, FDA improves by 19.5 points, 95% CI [13.5, 25.5]. There are 45 discordances favoring the refinement and six favoring the original prompt; exact p=1.83e-8 and two-model Holm-adjusted p=3.66e-8. The gain comes from substantially higher repair recall, but unsupported-repair rate rises by 6.3 points because the refined prompt attempts far more repairs.

For GPT-OSS 120B, FDA improves by 1.0 point, 95% CI [-1.0, 3.0]. Three discordances favor the refinement and one favors the original; exact and Holm-adjusted p=.625. This does not establish an accuracy improvement. UR falls from 2.9% to 1.0%.

On the development set used to design the prompt, Nano FDA rises from 88.75% to 98.75%, and GPT-OSS 120B from 98.125% to 100%. These are descriptive development results and are not independent evidence.

## Interpretation

The source-coverage instructions address Nano's tendency to abstain despite an explicit unused condition. They materially improve decision accuracy on the synthetic templates. The accompanying increase in unsupported repairs means the refinement is not yet a drop-in replacement for safety-sensitive use. GPT-OSS 120B was already near the ceiling, so this test has little room to show an accuracy gain.

These results do not replace the frozen MIRA confirmatory results. A new external, independently sourced and frozen benchmark is needed before claiming broad generalization.

## Reproducibility

- Synthetic test SHA-256: `8ba85d5370803b2084dbf03cd2c8bcb438d5497a2efc47597320fda382837a7e`
- Development complete SHA-256: `957258df04b93b2b48b772c4b72b27a3bf37a52adfa46ec4c7693559fdbf43f1`
- Synthetic-test complete SHA-256: `b500c5b710a360f22a8697425439798ef66d95f4dabe89718fd4f2fcf9ae3131`
- Analysis SHA-256: `909a5f73cac297db139e05dc723d3568b71d402dc179ee9f7769558bfe274665`

See `protocol.json`, `analysis.json`, `verification.json`, `by_family.json`, the complete JSONL files and raw attempt records in this directory. Transport errors were retained in attempt logs; all successful keys use their first valid response, without score-based resampling.
