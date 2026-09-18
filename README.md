# DeGro

**Target Determinacy Verification and Grounded Repair for Executable Mathematical Reasoning**

[Paper](paper/main.pdf) · [LaTeX source](paper/main.tex) · [Supplementary material](paper/supplementary_appendix.pdf) · [Reproduction](docs/reproduction.md)

## Abstract

Executable mathematical reasoning can run successfully while solving an
underconstrained or mistranslated problem. DeGro checks whether all feasible
assignments of a structured formalization agree on the requested target. When
they disagree, it produces two target-divergent witnesses and routes the problem
to a bounded, source-grounded repair-or-abstain policy. Proposed constraints must
pass provenance and formal acceptance checks before deployment. Controlled paired
evaluations and human-verified natural-error studies examine decision quality,
solver coverage, and the gap between ambiguity detection and successful repair.
Target determinacy is a guarantee about the encoded specification; it does not
establish that the specification faithfully represents the source.

## Method

Given constraints $F$ and target $q$, DeGro checks feasibility and then asks whether

$$
F(\mathbf{x}) \land F(\mathbf{x}') \land q(\mathbf{x}) \ne q(\mathbf{x}')
$$

is satisfiable. A satisfying assignment provides two witnesses with different
target values. An unsatisfiable query, after feasibility is established, certifies
target determinacy without requiring every variable to be uniquely determined.

1. **Diagnose.** Compile the specification to Z3 and check target determinacy.
2. **Ground.** Request a candidate constraint supported by an exact source span.
3. **Validate.** Check source provenance, consistency, non-redundancy, and restored target determinacy.
4. **Decide.** Accept an admissible repair; otherwise abstain from adding unsupported information.

The core returns five distinct statuses:

| Status | Interpretation |
| --- | --- |
| `DETERMINATE` | All feasible assignments agree on the target. |
| `AMBIGUOUS` | Two feasible assignments disagree on the target. |
| `INCONSISTENT` | No assignment satisfies the specification. |
| `UNKNOWN` | The solver did not reach a conclusive result. |
| `NOT_SUPPORTED` | The specification falls outside the supported expression fragment. |

`UNKNOWN` and `NOT_SUPPORTED` are never certificates of determinacy. A determinate
formalization can still contain incorrect constraints, domains, or targets.
Witnesses are audit evidence; the main four-method comparison supplies the repair
model with the ambiguity verdict rather than concrete witness values.

## Evaluation

### Controlled repair-or-abstain decisions

Each paired item shares a formalization and target across two source conditions:
a supported omission that should be repaired, and an underspecified source that
should trigger abstention. The four-method comparison separates determinacy
feedback from grounding:

| Paper label | Runner method | Determinacy feedback | Source grounding rule |
| --- | --- | :---: | :---: |
| Self-Review | `self_review` | — | — |
| Grounded Self-Review | `grounded_self_review` | — | ✓ |
| Determinacy-Guided Repair | `nonunique` | ✓ | — |
| DeGro | `nonunique_grounding` | ✓ | ✓ |

**MIRA** uses frozen 80/100/120-pair pilot, development, and fixed evaluation
splits. The fixed 120-pair results are distinguished from cumulative 300-pair
analyses. The GPT-OSS 120B substitution is post-hoc; later Nemotron comparisons
are exploratory.

**DRAW-Paired** extends the design to 350 natural algebra sources with injected
omissions. The current manuscript treats this cumulative experiment as post-hoc
and provisional: 300 pairs were author-reviewed after initial inference, and the
50-pair extension awaits review.

### Natural formalization errors

The consolidated study covers 795 solver-supported, conclusive formalizations:
292/500 MATH-500 problems and 503/514 ALG514 problems. Two human reviewers verified
AI-assisted labels. Separate pre-discussion labels were not preserved, so this
is human verification rather than independent double annotation. DRAW-1K
natural-error artifacts are excluded from this consolidated study.

### Metrics and reports

Repair success rate (**RSR**) measures correct grounded repair on omission cases;
correct abstention rate (**CAR**) measures correct abstention on underspecified
cases. Final decision accuracy (**FDA**) averages the two in the balanced paired
design. Unsupported-addition rate (**UR**) is measured among proposed additions.
Pair-level confidence intervals and paired tests accompany the comparisons.

| Evidence | Report |
| --- | --- |
| Natural-error coverage, labels, detection, and repair | [Consolidated study](results/natural_error_study_consolidated_report.md) |
| ALG514 natural errors | [ALG514 report](results/alg514_natural_error_report.md) |
| Exploratory 100-pair decision and witness ablations | [Decision baselines](results/decision_baselines_report.md) |
| Post-hoc Nemotron Nano comparison | [Nano report](results/nemotron_3_nano_30b_mira_report.md) |
| Post-hoc Nemotron Super comparison | [Super report](results/nemotron_3_super_mira_report.md) |
| Provisional 300-pair DRAW-Paired stage | [DRAW-Paired report](results/draw_paired_provisional300_report.md) |
| Exploratory source-coverage prompt refinement | [Refinement report](results/degro_v2/report.md) |

## Reproduction

Requires **Python 3.11 or later**. The package is named `targetcheck`.

```bash
python3 -m venv .venv
.venv/bin/pip install -e '.[dev]'
.venv/bin/pytest
.venv/bin/python scripts/check_jsonl.py data/paired/demo.jsonl
```

For hosted inference, place one Ollama Cloud API key per line in the Git-ignored
`api.txt`, then run the one-pair smoke experiment:

```bash
./scripts/run_smoke.sh
```

Provider setup, experiment commands, annotation workflows, and retry behavior are
in the [reproduction guide](docs/reproduction.md). The natural-error taxonomy and
annotation policy are in the [study protocol](paper/natural_error_protocol.md).

To build the paper with `latexmk` and a LaTeX installation:

```bash
make -C paper
```

## Repository Structure

| Path | Contents |
| --- | --- |
| [`targetcheck/`](targetcheck/) | Specification schema, Z3 compiler, determinacy checks, grounding gate, and model clients |
| [`scripts/`](scripts/) | Dataset preparation, experiment runners, annotation tools, and analyses |
| [`tests/`](tests/) | Tests for the solver core and research pipeline |
| [`data/`](data/) | Paired datasets and natural-error study artifacts |
| [`results/`](results/) | Raw responses, manifests, analyses, and reports |
| [`paper/`](paper/) | Manuscript, supplementary material, figures, and research log |
| [`docs/`](docs/) | Detailed reproduction workflows |
