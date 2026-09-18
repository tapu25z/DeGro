# Nano thinking-level capability probe

Date: 2026-09-18. This is a diagnostic probe, not a main experiment.

Model: `nemotron-3-nano:30b` through Ollama Cloud. Method: `nonunique_grounding`.
Four previously inspected MIRA pairs (eight cases) were evaluated at each requested
level, for 24 requests total. Temperature was 0 and requested seed was 42 to reduce
sampling variation; cloud reproducibility and enforcement of the seed are not verified.
The main experiment uses temperature 1.0, so these results must not replace its scores.

| Requested think | Correct cases | Correct OMISSION repairs | UNDERSPECIFIED abstentions |
|---|---:|---:|---:|
| low | 6/8 | 2/4 | 4/4 |
| medium | 7/8 | 3/4 | 4/4 |
| high | 7/8 | 3/4 | 4/4 |

All 24 requests succeeded. Cases were selected for diagnosis, not representative estimation.

Ollama's public Nemotron 3 Nano renderer resolves thinking with `ThinkValue.Bool()`;
low, medium and high are all true. Its medium-effort branch is gated on the distinct
Nemotron 3.5 renderer, not Nemotron 3 Nano. The registry configuration for the `30b`
tag identifies the renderer as `nemotron-3-nano`. This is evidence that the three
requested levels do not constitute three distinct effort settings for this model.
The deployed cloud implementation/version is not directly inspectable.

Differences in individual responses therefore do not establish a causal effect of
thinking effort. A three-level full-data run was not launched, and paper/main results
were not modified. A thinking on/off comparison or a budget experiment requires a
separately specified, supported intervention.

Sources:
- https://github.com/ollama/ollama/blob/main/model/renderers/nemotron3nano.go
- https://github.com/ollama/ollama/blob/main/api/types.go
- https://registry.ollama.ai/v2/library/nemotron-3-nano/manifests/30b

Records: `results/nano_think_levels_probe.jsonl`.
