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
- MATH-500 natural-error cohort: 292 conclusive solver-supported GPT-OSS 20B
  formalizations frozen from 500 problems. Two human reviewers checked all 292
  Gemma 4 31B proposals and accepted them without changes. Final labels are 158
  correct, 69 wrong-target, 32 wrong-constraint, 24 missing-constraint, eight
  extra-constraint, and one wrong-domain. Verified-label SHA-256:
  `4e1bbe0b9eaefdefe4569ec10fdd42daf8f1131d17dfbc410d0faed0b430ad38`.
  Separate pre-discussion human label files were not retained, so do not report
  human Cohen's kappa or call the process independent double annotation.
- MATH-500 human-verified results: missing-constraint detection recall 87.5%
  (21/24), precision 17.4% (21/121), end-to-end missing-constraint repair 4.2%
  (1/24), Structured Solver accuracy 49.3% (144/292), and DeGro accuracy 53.8%
  (157/292). Sixteen discordant cases favor DeGro and three favor the baseline;
  exact McNemar p=0.00443. All prevalence statements must note 58.4% coverage.

## DRAW-1K natural-error run — excluded from paper (2026-09-11)

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

## DRAW-1K natural-error run — excluded from paper (2026-09-11)

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

## ALG514 human-verified natural-error study (2026-09-11)

- The full official ALG514 release was run with one GPT-OSS 20B joint-target
  formalization per problem. The verifier-supported frozen cohort contains
  503/514 problems (97.86% coverage); six solver-level unsupported, one
  model-declared unsupported, and four inconsistent cases were excluded before
  annotation.
- GPT-OSS 120B proposed labels for all 503 cases and performed a final pass on
  all 22 semantic/verifier disagreements. Two human reviewers then reviewed the
  complete final label set and accepted 503/503 without changes.
- This is a full two-person verification of AI-assisted labels, not independent
  blinded double annotation. Separate pre-discussion human label files were not
  recorded, so Cohen's kappa must not be reported.
- Final labels: 477 correct, 11 wrong target, eight target-critical missing
  constraint, and seven wrong constraint. The human-verified semantic-error
  rate is 26/503 (5.17%); the target-critical omission rate is 8/503 (1.59%).
- The verified-label artifact SHA-256 is
  `72217047ff8d41b4a3766e504325821bd07230d7b6dc7636475294ab8e5ffecd`.
- ALG514-compatible numerical scoring treats requested target values as a
  multiset subset of the release's all-unknown solution vector and uses a
  `1e-3` tolerance for rounded answers. Structured Solver scores 484/514
  (94.16%); DeGro scores 485/514 (94.36%). Nine numerically compatible cases
  still contain a verified semantic error, showing that answer accuracy hides
  representation failures.

## Immediate experiment checklist

1. Import MIRA-Math and document its license/revision hash.
2. Freeze compatible families and deterministic exclusion reasons.
3. Generate 80 validated pairs and save a dataset manifest hash.
4. Freeze repair prompts and JSON schemas before inspecting method comparisons.
5. Run Self-Review, NonUnique, TargetWitness, and TargetCheck on GPT-OSS 20B.
6. Compute paired confidence intervals and preregistered McNemar comparisons.
7. Apply the go/no-go threshold before scaling to 120B and Gemma 4 31B.
