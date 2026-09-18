# DeGro

DeGro asks whether every satisfying assignment of a structured mathematical formalization agrees on the requested target. If not, it returns two feasible assignments with different target values. These witnesses can drive a source-grounded repair-or-abstain loop.

This repository contains the solver core, grounding gate, paired-data schema,
tests, a paper draft, and a completed 100-pair GPT-OSS 20B experiment.

## Quick start

```bash
python3 -m venv .venv
.venv/bin/pip install -e '.[dev]'
.venv/bin/pytest
.venv/bin/python scripts/check_jsonl.py data/paired/demo.jsonl
```

For Ollama Cloud, put one API key per line in the Git-ignored `api.txt`, then run:

```bash
.venv/bin/python scripts/ollama_smoke.py --list-only
.venv/bin/python scripts/ollama_smoke.py --model gpt-oss:20b
```

The client rotates across accounts only on authentication, quota, or rate-limit responses (HTTP 401/402/403/429). Logs contain a one-based account index and status, never the key value.

### Run the core nine-method smoke experiment

The default smoke test runs one paired item: two source conditions times nine methods, for eighteen API calls.

```bash
./scripts/run_smoke.sh
```

To smoke-test three pairs (54 calls):

```bash
./scripts/run_smoke.sh 3
```

Optional overrides:

```bash
TARGETCHECK_MODEL='gpt-oss:20b' \
TARGETCHECK_KEYS_FILE='/absolute/path/to/api.txt' \
./scripts/run_smoke.sh 1
```

Each run gets a UTC timestamp, so it never silently reuses a previous smoke result. Raw responses go under `results/raw/`; the printed TSV summary is saved under `results/`.

### Build and run the held-out confirmation set

The held-out builder excludes every pilot pair, adds a fifth compatible family,
stratifies toward difficulty 2--3, and randomizes source-sentence order.

```bash
.venv/bin/python scripts/build_heldout_mira.py
./scripts/run_heldout_background.sh
```

The confirmatory run uses six methods. `random_pair` remains available for
diagnostics, but is excluded because every pair of distinct feasible assignments
in the current one-degree-of-freedom benchmark also differs on the target.

Run the two decision baselines on the same 100 pairs with:

```bash
./scripts/run_decision_baselines.sh
```

These add `grounded_self_review` (grounding without solver information) and
`minimal_witness_grounding` (minimal target-divergent witness plus grounding).
The runner resumes completed calls and writes a combined 1,600-record analysis
to `results/gpt_oss_20b_decision_analysis.json`.

### Run the blinded natural-error study

The natural-error study reuses the single initial formalization shared by the
MATH-500 structured methods. It freezes a packet that hides detector and repair
outcomes, validates two independent annotation passes, and then joins only the
resolved labels back to the run results:

```bash
.venv/bin/python scripts/build_natural_error_study.py \
  'results/raw/gpt-oss_20b_math500_six_methods_low_full_v2_shard*.jsonl' \
  --out-dir data/natural_errors/gpt_oss_20b_math500

# Complete annotations_a.jsonl and annotations_b.jsonl independently.
.venv/bin/python scripts/adjudicate_natural_errors.py \
  data/natural_errors/gpt_oss_20b_math500/annotations_a.jsonl \
  data/natural_errors/gpt_oss_20b_math500/annotations_b.jsonl \
  --disagreements data/natural_errors/gpt_oss_20b_math500/disagreements.jsonl \
  --agreement-out results/natural_error_agreement.json

# Fill each disagreement's resolution object in a third pass, then merge.
.venv/bin/python scripts/resolve_natural_errors.py \
  data/natural_errors/gpt_oss_20b_math500/annotations_a.jsonl \
  data/natural_errors/gpt_oss_20b_math500/annotations_b.jsonl \
  --resolutions data/natural_errors/gpt_oss_20b_math500/disagreements.jsonl \
  --out data/natural_errors/gpt_oss_20b_math500/resolved_annotations.jsonl

# Join the resolved labels to outcomes and analyze.
.venv/bin/python scripts/analyze_natural_error_study.py \
  'results/raw/gpt-oss_20b_math500_six_methods_low_full_v2_shard*.jsonl' \
  --annotations data/natural_errors/gpt_oss_20b_math500/resolved_annotations.jsonl \
  --out results/natural_error_study.json
```

The frozen taxonomy, blinding rules, estimands, and reporting policy are in
`paper/natural_error_protocol.md`. `UNSURE` labels and mismatched IDs stop the
pipeline rather than being silently excluded.

For the lower-effort, fully disclosed workflow, generate independent GPT-OSS
and Gemma proposals on the same frozen packet, then build a human queue containing
every model disagreement and a deterministic 20% audit of model consensus:

```bash
./scripts/run_natural_preannotation.sh
MODEL='gemma4:31b' \
REVIEW_OUT='data/natural_errors/gpt_oss_20b_math500/gemma4_31b_ai_assisted_human_review.jsonl' \
./scripts/run_natural_preannotation.sh

.venv/bin/python scripts/build_dual_ai_review.py \
  data/natural_errors/gpt_oss_20b_math500/gpt_oss_20b_ai_assisted_human_review.jsonl \
  data/natural_errors/gpt_oss_20b_math500/gemma4_31b_ai_assisted_human_review.jsonl \
  --packet data/natural_errors/gpt_oss_20b_math500/adjudication_packet.jsonl \
  --out data/natural_errors/gpt_oss_20b_math500/dual_ai_human_review.jsonl

# Fill each required resolution object, then finalize.
.venv/bin/python scripts/finalize_dual_ai_review.py \
  data/natural_errors/gpt_oss_20b_math500/gpt_oss_20b_ai_assisted_human_review.jsonl \
  data/natural_errors/gpt_oss_20b_math500/gemma4_31b_ai_assisted_human_review.jsonl \
  data/natural_errors/gpt_oss_20b_math500/dual_ai_human_review.jsonl \
  --out data/natural_errors/gpt_oss_20b_math500/resolved_annotations.jsonl
```

The final records distinguish human-adjudicated, human-audited, and unaudited
AI-consensus labels. The finalizer rejects unresolved required reviews.

### DRAW-1K natural-error study

DRAW-1K is the preferred ecological-validity benchmark because it contains
general algebra word problems with gold equation systems and derivation
alignments. Fetch the official release and run the untouched 200-problem test
split with joint-target verification (both requested unknowns must be unique):

```bash
.venv/bin/python scripts/fetch_draw1k.py
./scripts/run_draw1k_natural.sh
```

This freezes only conclusive solver-supported initial formalizations. Generate
the two independent blinded annotation passes on that exact packet with:

```bash
PACKET='data/natural_errors/gpt_oss_20b_draw1k_test/adjudication_packet.jsonl' \
EXPECTED=194 \
PREANNOTATION_STEM='gpt_oss_20b_draw1k_natural_preannotation_low' \
REVIEW_OUT='data/natural_errors/gpt_oss_20b_draw1k_test/gpt_oss_20b_annotations.jsonl' \
./scripts/run_natural_preannotation.sh

MODEL='gemma4:31b' \
PACKET='data/natural_errors/gpt_oss_20b_draw1k_test/adjudication_packet.jsonl' \
EXPECTED=194 \
PREANNOTATION_STEM='gemma4_31b_draw1k_natural_preannotation_low' \
REVIEW_OUT='data/natural_errors/gpt_oss_20b_draw1k_test/gemma4_31b_annotations.jsonl' \
./scripts/run_natural_preannotation.sh
```

### Run the four-method MIRA ablation

The current comparison uses the same four methods for GPT-OSS 20B and
GPT-OSS 120B:

| Paper label | Runner method |
|---|---|
| Self-Review | `self_review` |
| Grounded Self-Review | `grounded_self_review` |
| Determinacy-Guided Repair | `nonunique` |
| DeGro | `nonunique_grounding` |

Run GPT-OSS 120B on the frozen pilot, development, and confirmatory splits:

```bash
./scripts/run_gpt_oss_120b_mira.sh
.venv/bin/python scripts/assemble_mira_full300.py
```

The runner resumes successful records, makes a second retry pass, and produces
complete and analyzed files for every split. The GPT-OSS 20B files are reused
without new inference calls. The 120B model substitution was chosen after the
original two-model plan; its confirmatory-set results are reported as a
post-hoc model comparison.

### Additional Nemotron comparisons

```bash
zsh scripts/run_nemotron_3_nano_30b_mira.sh
zsh scripts/run_nemotron_3_super_mira.sh
.venv/bin/python scripts/assemble_mira_full300.py --models nemotron_3_nano_30b
```

This post-hoc comparison retains the frozen 80/100/120-pair splits, four
methods, prompts, temperature 1.0, and API `think="medium"` request. Equal
API requests do not establish equal internal reasoning budgets. The runner
resumes the first valid response, retries transport failures with account
failover, and refuses to analyze incomplete splits. Raw responses and a
run manifest accompany the split and cumulative analyses.

On the fixed 120-pair set, DeGro reaches 90.8% FDA versus 89.6% for grounded
self-review (+1.25 points, pair-cluster 95% CI [-2.5, 5.0], exact McNemar
p=0.664). This is statistically inconclusive; DeGro reaches 100% CAR, while
grounded self-review already reaches 98.3% CAR. Both later Nemotron tests are
exploratory and separate from the original two-test GPT-OSS Holm family.

For Super, fixed-set DeGro FDA is 90.8% versus 86.3% grounded self-review
(+4.58 points, 95% CI [0.0, 9.2], exact p=.0801), statistically inconclusive.
Verdict-only repair scores highest at 91.3%. The full 300-pair Super comparison
is secondary: 89.8% versus 84.2% (+5.67, CI [2.5, 8.7], p=.000509).
All 2400 expected records are valid; the report and manifest accompany results.

## Exploratory source-coverage refinement

A prompt refinement developed from the 80-pair development errors now asks the
repair model to audit every source condition against the formalization and makes
the already enforced variable domains explicit. Its frozen comparison is in
`results/degro_v2/`: 320 development responses and 800 new-test responses are
complete and independently verified. On a separate 100-pair synthetic stress
set, Nano 30B FDA changes from 75.5% to 95.0% (+19.5 points, 95% CI
[13.5, 25.5], Holm-adjusted p<.001), while GPT-OSS 120B changes from 98.5% to
99.5% (+1.0 point, CI [-1.0, 3.0], adjusted p=.625). Nano UR rises from 1.9%
to 8.2%, so the gain comes with more unsupported repairs. This is an exploratory
synthetic evaluation, not a replacement for the frozen MIRA confirmatory results.

## Soundness boundary

`DETERMINATE` proves only that all models of the current formalization agree on the target. It does not prove that the formalization faithfully translates the natural-language source. `UNKNOWN` and `NOT_SUPPORTED` are never treated as proofs of determinacy.

## Research status

- Implemented: integer/real/Boolean variables, arithmetic constraints, finite domains, duplicated-model determinacy query, divergent witness extraction, consistency/non-redundancy/source-span repair gate.
- Current held-out result: `nonunique_grounding` reaches 98.5% FDA and
  `minimal_witness_grounding` reaches 98.0% FDA. The witness has no measurable
  incremental value on this benchmark (paired McNemar p=1.0).
- Next: pivot the benchmark toward multiple source-supported missing facts where
  only one fact is target-critical, then test when witnesses help beyond grounding.
- Submission deadline checks and AI-use disclosure are documented in `paper/research_log.md`.
