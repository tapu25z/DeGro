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

## Current 350-pair cumulative experiment

- `draw_paired.jsonl`: the original 300 pairs / 600 cases, author-reviewed
  after provisional inference. Two title-abbreviation spans were corrected;
  affected responses were rerun. This original cohort is preserved.
- `draw_paired_extension50.jsonl`: 50 additional pairs / 100 cases, with
  disjoint source indices. The extension is locked before its own inference,
  but selected after the original outcomes. Human review is pending.
- `draw_paired_extension50_review.jsonl`: review only these 50 new spans and
  deletions. Solver checks do not establish that the deletion preserves meaning.
- `draw_paired350.jsonl`: combined 350 pairs / 700 cases (260 train-derived,
  90 dev-derived). `cohort` and `dataset_stage` preserve the different review
  status; this is not a fully human-reviewed dataset yet.
- `draw_paired350.manifest.json`: selection seed, hashes, counts and review status.

The extension uses seed 20260919 and proportional train/dev allocation from
67 remaining unflagged proposals, selecting 37 train-derived and 13 dev-derived
sources without inspecting their model outcomes. DRAW-1K test sources remain unused.
The cumulative analysis is post-hoc, not a new confirmatory test.

Complete results are kept separately under `results/*_draw_paired350_complete.jsonl`
(2,800 records per model: 700 cases x four policies). Original
`results/*_draw_paired300_complete.jsonl` files are not overwritten. Transport
retries retain the first valid response, never the highest-scoring response.
