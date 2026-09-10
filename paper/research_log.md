# Research and submission log

## Verified submission constraints (2026-09-09)

- AAMAS 2027 main-track papers: English, double blind, PDF, LaTeX mandatory, at most 8 content pages plus references.
- OpenReview account deadline: 2026-09-17; abstract: 2026-10-01; paper: 2026-10-08 (AoE).
- AI-assisted hypothesis/methodology/experimental design requires disclosure of the tool, version, and prompt. AI tools cannot be authors. Authors remain responsible for citations and accuracy.
- Primary source: https://warwick.ac.uk/fac/sci/dcs/aamas2027/calls/instructions/

## AI-assisted research disclosure (draft for supplement)

An AI coding assistant (OpenAI Codex; model/version to be copied from the final run metadata) was used on 2026-09-09 to help convert an author-provided research blueprint into a prototype implementation, an experimental scaffold, and an initial manuscript draft. The representative user prompt was: “xem và làm paper này” (“review and develop this paper”), followed by a request to configure three Ollama Cloud accounts for quota failover. The authors must independently verify the hypotheses, methodology, implementation, literature, data, statistical analyses, and every statement in the submitted manuscript. The assistant is not an author. This disclosure must be updated with exact product/model metadata before submission.

## Evidence status

- Solver core: implemented and unit-tested.
- Ollama Cloud: authenticated smoke test completed with `gpt-oss:20b`; secret values were not logged.
- Literature metadata: checked against arXiv pages for SymCode, MIRA-Math, ReLoop, SymDiag, and minimal-core repair.
- Natural-error cohort: 292 conclusive solver-supported GPT-OSS 20B
  formalizations frozen from the 500-problem MATH-500 run. The blinded packet
  SHA-256 is `a7f16240f80c9838a6823516760c6754f8787dc2ebb57626c710c804e352e063`.
  Independent blinded pre-annotation is complete for GPT-OSS 20B and Gemma 4
  31B using shared prompt SHA-256
  `0f1093c9156904da78890ca09e9dc2048b4adf2541e14a103136e0bf03b7e094`.
  Exact label agreement is 67.8% (Cohen's kappa 0.458); agreement on membership
  in the target-critical missing-constraint subset is 90.8%. Human resolution
  is pending for 94 disagreements, plus a frozen audit of 44 consensus cases.
  These are annotation-process diagnostics, not natural-error results.
- Quantitative paper results: controlled-study results exist, but natural-error
  results are **not yet collected**. Do not add natural-error numbers to
  `main.tex` until required human adjudication and audit finish.

## DRAW-1K natural-error run (2026-09-11)

- Official release 0.7 downloaded from Microsoft; archive SHA-256:
  `de415ed5d7182c6b4000ec648fbb57b19345f2adc67a69cd95e09912534ec92f`.
- Untouched test split: 200 problems. GPT-OSS 20B generated one shared
  formalization per problem. A conclusive solver-supported cohort of 194 was
  frozen with packet SHA-256
  `4539aa81fc43aca4a622a3d5409d1f9c775a611d992ace40063062960f5c808e`;
  five inconsistent and one unsupported specification were excluded.
- Provisional pre-adjudication performance: Structured Solver 69.5%, DeGro
  72.0%, joint verifier coverage 97%. Do not cite these as final: unordered
  two-answer questions and division-at-zero semantics require a verifier
  correction and outcome recomputation from the frozen specifications.
- Blinded annotation proposals are complete for GPT-OSS 20B, Gemma 4 31B, and
  GPT-OSS 120B. GPT-OSS 120B proposed 177 correct, 6 wrong-constraint, 8
  wrong-target, and 3 extra-constraint labels; it proposed no missing-constraint
  cases. This is a model-generated proposal distribution, not ground truth.
  Exact agreement with GPT-OSS 20B is 91.8% and with Gemma 4 31B is 90.2%; the
  low kappa values (0.185 and 0.209) reflect severe correct-label prevalence.

## DRAW-1K natural-error run (2026-09-11)

- Official Microsoft release 0.7 downloaded from the publisher archive;
  archive SHA-256:
  `de415ed5d7182c6b4000ec648fbb57b19345f2adc67a69cd95e09912534ec92f`.
- The untouched test split contains 200 problems. One shared GPT-OSS 20B
  formalization was generated per problem; 194 had a conclusive supported
  solver verdict and were frozen in the blinded packet with SHA-256
  `4539aa81fc43aca4a622a3d5409d1f9c775a611d992ace40063062960f5c808e`.
- Provisional pre-audit snapshot: Structured Solver 69.5% accuracy; DeGro 72.0%;
  joint verifier coverage 97%; 12 ambiguity triggers and 6 accepted repairs.
  These are not paper-ready results.
- Audit discovered that per-position target determinacy is too strict for
  DRAW-1K's order-invariant two-answer evaluation. Symmetric target swaps must
  be verified as an unordered multiset. Reciprocal work-rate encodings also
  require explicit positive-time domains to exclude SMT division-by-zero
  models. Recompute verifier and repair outcomes from the frozen initial
  formalizations before reporting final numbers; do not regenerate or select
  initial specifications based on this audit.
- Blinded GPT-OSS and Gemma pre-annotations completed for all 194 frozen cases.
  Their preliminary agreement cannot substitute for human adjudication,
  especially because neither annotator caught the above solver-semantic issue.

## Immediate experiment checklist

1. Import MIRA-Math and document its license/revision hash.
2. Freeze compatible families and deterministic exclusion reasons.
3. Generate 80 validated pairs and save a dataset manifest hash.
4. Freeze repair prompts and JSON schemas before inspecting method comparisons.
5. Run Self-Review, NonUnique, TargetWitness, and TargetCheck on GPT-OSS 20B.
6. Compute paired confidence intervals and preregistered McNemar comparisons.
7. Apply the go/no-go threshold before scaling to 120B and Gemma 4 31B.
