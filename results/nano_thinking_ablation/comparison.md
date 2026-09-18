# Nano thinking on/off: MIRA-300

Fresh runs, temperature 1.0; same frozen 300 pairs, four methods and scorer.

| Method | FDA on | FDA off | RSR on | RSR off | CAR on | CAR off | FDA delta on−off (95% pair CI) |
|---|---:|---:|---:|---:|---:|---:|---|
| self_review | 87.2 | 42.8 | 79.7 | 6.0 | 94.7 | 79.7 | +44.3 [+40.5, +48.0] |
| grounded_self_review | 90.8 | 47.2 | 83.0 | 3.0 | 98.7 | 91.3 | +43.7 [+40.8, +46.5] |
| nonunique | 73.5 | 48.2 | 52.3 | 1.7 | 94.7 | 94.7 | +25.3 [+22.2, +28.7] |
| nonunique_grounding | 90.0 | 49.3 | 80.0 | 0.3 | 100.0 | 98.3 | +40.7 [+38.3, +42.8] |

All rates are percentages; deltas are percentage points.

## DeGro family-level repair success

| Family | RSR thinking on | RSR thinking off |
|---|---:|---:|
| crt_reconstruction | 81.7 | 1.7 |
| graph_path_sums | 95.0 | 0.0 |
| linear_system_separator | 93.3 | 0.0 |
| moment_problem | 96.7 | 0.0 |
| rankdef_linear_shared | 33.3 | 0.0 |

## DeGro errors and token usage

| Measure | Thinking on | Thinking off |
|---|---:|---:|
| omission_abstains | 57 | 297 |
| omission_invalid_adds | 3 | 2 |
| underspecified_adds | 0 | 5 |
| median_eval_count | 656.5 | 27.0 |
| thinking_nonempty_cases | 600 | 0 |
| total_attempts | 601 | 608 |
| first_attempt_FDA_counting_errors_as_wrong | 89.83333333333333 | 49.166666666666664 |

## Interpretation limits

Single stochastic run per mode; no claim about multi-run variance.
Primary metrics use the first valid response with bounded retries, matching the existing main-run policy; first-attempt errors and FDA are also reported.
Unfinished jobs were re-sharded after latency imbalance; interrupted requests and service rate limits are documented in scheduling_notes.md. Wall latency and first-attempt service errors are descriptive, not controlled speed/robustness benchmarks.
FDA inference clusters both labels within each pair.
Four FDA comparisons receive Holm correction; RSR/CAR are diagnostic.
Main paper results are unchanged.

See comparison.json for UR, token counts, family-level RSR, paired transitions and corrected p-values.
