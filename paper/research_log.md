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

## GPT-OSS 120B replacement run (2026-09-16)

- Replaced the submitted-paper Gemma comparison with a fresh GPT-OSS 120B run using the same frozen MIRA splits, prompts, temperature 1.0, and medium reasoning effort.
- Completed 640 pilot, 800 development, and 960 fixed-set records with no missing or error records; the combined file contains 2,400 records.
- On the fixed 120-pair set, DeGro improves FDA from 87.5% to 93.8% over grounded self-review (+6.25 points; pair-bootstrap 95% CI [1.7, 10.8]; exact McNemar p=.0135). The model substitution is disclosed as post-hoc.
- A fresh blinded GPT-OSS 120B MATH-500 proposal pass completed all 292 cases and agrees with the human-verified primary labels on 207/292 (70.9%). Human labels were not replaced without renewed reviewer adjudication.

## Nemotron 3 Nano 30B additional comparison (2026-09-17)

- Completed the same frozen four-method MIRA benchmark: 640 pilot, 800 development, 960 fixed-set records, 2,400 total; no missing or unresolved error records in finalized outputs.
- Same frozen prompts, temperature 1.0, and API `think="medium"` request. Equal API requests do not establish equal model reasoning budgets. The additional model was selected post-hoc.
- Fixed-set DeGro FDA 90.83% versus grounded self-review 89.58%: +1.25 points, pair-cluster 95% CI [-2.5, 5.0], exact McNemar p=.6636 (12 versus 9 discordances). CAR 100.0% versus 98.33%; RSR 81.67% versus 80.83%; UR 1/99 versus 3/100. No statistically established incremental FDA benefit.
- Cumulative FDA 90.33% versus 89.50%: +0.83 points, CI [-1.5, 3.3], exact p=.5901. This secondary analysis includes development data.
- Sensitivity Holm over all three model tests gives p=.1002 (20B), .0406 (120B), .6636 (Nemotron); retain the original two-GPT-OSS family separately.
- Transport workers were repartitioned and quota failures retried through account failover; every prior valid response was preserved, without score-based resampling. All frozen input hashes, raw configurations, expected unique keys, and recomputed scores were checked.
- Added results and limitations to main paper and supplementary appendix; model source: NVIDIA, arXiv:2512.20848.

## Nemotron 3 Super additional comparison (2026-09-17)

- Completed all 2,400 records on the same frozen four-method MIRA benchmark: 640 pilot, 800 development, 960 fixed-set records. Exactly 2,400 successful raw records, zero error records; all expected keys and independently recomputed scores verified.
- Same prompts, temperature 1.0, and API `think="medium"`; post-hoc model addition. Ollama reports tag digest `da11955bb451`. Equal API requests do not establish equal internal reasoning budgets.
- Fixed-set DeGro FDA 90.83% versus grounded self-review 86.25%: +4.58 points, pair-cluster 95% CI [0.0, 9.17], exact McNemar p=.080143 (22 versus 11 discordances), statistically inconclusive. RSR 84.17% versus 74.17%; CAR 97.50% versus 98.33%; UR 5/106 versus 4/93. Verdict-only repair scores highest at 91.25%.
- Full300 DeGro FDA 89.83% versus 84.17%: +5.67 points, CI [2.5, 8.67], p=.000509; verdict-only FDA 91.50%. This includes development observations and does not replace fixed-set inference.
- Holm sensitivity over all four model tests: 20B .1503, 120B .0541, Nano .6636, Super .1603; none below .05. Original two-GPT-OSS family remains separately reported.
- Main paper and supplement now include all four models, inconclusive fixed-set Super inference, and its verdict-only advantage. One-decimal values use half-up rounding; GPT-OSS 120B verdict-only FDA 91.25% now displays as 91.3% instead of 91.2%, without changing any underlying outcome.


### 2026-09-17: DeGro source-coverage audit candidate

User requested improvement for Nemotron3Nano30B and GPT-OSS120B. Designed one candidate from pilot80 only; original scorer and prompts unchanged. Registered protocol and synthetic100-pair stress test in `results/degro_v2/`. Original MIRA compatible pool exhausted; new data explicitly synthetic. All200 gold decisions rescored correct, no exact source overlap with original300. Eight prompt tests pass. Evaluation currently blocked: all17 accounts return429, including single-request check after pausing concurrent Ultra/experiment workers. Zero successful candidate outputs; no improvement or significance claim and no paper table update. Resume command and details in `results/degro_v2/report.md`.

### 2026-09-17: DeGro source-coverage audit completed

The previously rate-limited Nano 30B/GPT-OSS 120B experiment resumed and completed. Verified 320/320 development responses and 800/800 synthetic-test responses; every score was independently recomputed and every finalized row is the first valid response for its key. On the frozen synthetic 100-pair stress set, Nano FDA changed from 75.5% to 95.0% (+19.5 points, pair-cluster 95% CI [13.5,25.5], exact p=1.83e-8, two-model Holm p=3.66e-8). Nano UR increased from 1/53 (1.9%) to 8/98 (8.2%), an explicit repair-risk tradeoff. GPT-OSS 120B changed from 98.5% to 99.5% (+1.0, CI [-1.0,3.0], p=.625), with UR 3/102 to 1/101. The data are generated from the same algebraic templates because the original compatible MIRA pool is exhausted; they are not an external benchmark and do not replace confirmatory results. Main paper and supplement label this analysis exploratory.
