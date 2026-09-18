# DRAW-Paired construction

This directory is intentionally split into two stages.

## 1. Solver-verified candidates

Run:

```bash
.venv/bin/python scripts/build_draw_paired.py
```

The builder reads only the DRAW-1K `train` and `dev` splits. For every source
problem, it checks that the full gold equation system determines the selected
target, that the value agrees with a published gold solution, and that deleting
one equation leaves a satisfiable system in which the target is ambiguous.

Outputs:

- `candidates.jsonl`: automatic mathematical checks and a proposed text span.
- `review_packet.jsonl`: the same records with blank human-review fields,
  ordered with unflagged proposals first and flagged reserve cases afterward.
- `candidate_manifest.json`: counts and SHA-256 hashes.

These files are **not a frozen evaluation dataset**. A clean automatic span is
only a review aid, not a human approval.

For inference engineering before review is complete, the repository may contain
`draw_paired_provisional_300.jsonl`. Its cohort is locked before outcomes and its
oracle actions pass the released scorer, but it must remain explicitly marked
provisional until the exact spans and deletions are human-approved.

## 2. Human review and freeze

For each row in `review_packet.jsonl`, set `review.status` to `APPROVE` or
`REJECT`. An approval must also provide:

- `reviewer`: reviewer identifier;
- `source_span_exact`: the exact, unique substring supported by the removed
  equation;
- `underspecified_problem`: the original problem with exactly that substring
  deleted;
- `meaning_preserved_after_deletion: true`;
- optional `notes`.

Reject a row if the supporting text cannot be removed without also deleting a
retained constraint, the question, referents needed by the remaining text, or
other essential semantics. Flags such as `span_also_supports_retained_equation`
identify cases that need particular care.

After every row has been reviewed, run:

```bash
.venv/bin/python scripts/finalize_draw_paired.py
```

The finalizer re-runs the solver checks, validates the exact deletion, emits the
`OMISSION` and `UNDERSPECIFIED` cases, and writes a frozen manifest. It refuses
to freeze a packet with pending reviews by default.

## Current retained 300-pair experiment

The original cumulative pool contained 350 pairs (300 initial plus 50 extension).
After the author's data re-review, 50 pairs were excluded: 44 initial and six
extension pairs. The retained pool contains 300 pairs / 600 cases, from 221
training and 79 development sources. DRAW-1K test sources remain unused.

- `excluded_pair_ids.txt`: exact author-supplied exclusion list (case-sensitive).
- `exclusion_audit.json`: timing, cohort counts and counts of removed records;
  no excluded responses are retained in this audit.
- `draw_paired.jsonl`: 256 retained initial pairs / 512 cases.
- `draw_paired_extension50.jsonl` and `draw_paired_extension50_reviewed.jsonl`:
  44 retained extension pairs / 88 cases; model inputs remain unchanged.
- `draw_paired350.jsonl`: 300 retained pairs / 600 cases. Its legacy filename
  identifies the original cumulative experiment, not its current size.
- Review packets retain the exclusions as author `REJECT` decisions.
- Manifests contain current counts, hashes and the exclusion audit reference.

Each model's `results/*_draw_paired350_complete.jsonl` contains 2,400 retained
records (600 cases x four policies). The 50 excluded pairs' records are removed
from complete outputs, raw outputs and exported result CSVs. Initial and
provisional cohort filenames likewise retain their historical names; their
current counts are 256 pairs and 2,048 complete records per model.

The extension used seed 20260919 and was selected after initial outcomes.
Review and exclusions followed inference and access to model results; retained
subset analyses are post-hoc. No item-specific exclusion rationale was supplied.
Use `scripts/prune_draw_paired.py` to reapply the exclusion list and
`scripts/report_draw_paired350.py` to validate retained provenance.
