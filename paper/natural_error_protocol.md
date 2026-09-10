# Natural-error study protocol

This protocol is frozen before human labels are joined to detector or repair
outcomes. Its purpose is to test ecological validity: whether target-critical
under-formalization occurs in model-generated specifications of complete,
naturally written problems, and whether TargetCheck detects and repairs it.

## Cohort and unit of analysis

- Generate exactly one initial Structured SymCode formalization per problem.
- Reuse that same formalization for Structured Solver and DeGro. The unit of
  analysis is the original problem, not a method call.
- Include every successfully parsed, solver-supported initial formalization in
  the frozen cohort. Record exclusions by deterministic reason.
- Hash the blinded packet before annotation. Do not select cases based on the
  detector verdict, repair action, or final accuracy.

## Blinding and AI-assisted human verification

Two annotation models independently propose a label, evidence, and confidence from the
complete source problem, reference solution, reference answer, and generated
formalization. They do not see the determinacy verdict, witness, method name,
repair proposal, or method outcome. A human adjudicates every model
disagreement and audits all consensus `MISSING_CONSTRAINT` cases plus a frozen,
label-stratified 20% sample of the remaining consensus cases. Unreviewed model
consensus remains explicitly marked as such in the released labels. The final
analyzer refuses unresolved required reviews. Do not describe the corpus as
independently human-annotated or fully human-verified.

Choose one primary label:

- `CORRECT`: the specification faithfully represents the target-relevant task.
- `MISSING_CONSTRAINT`: a source-supported, target-critical condition is absent.
- `WRONG_CONSTRAINT`: a represented relation mistranslates the source.
- `EXTRA_CONSTRAINT`: the model adds an unsupported assumption.
- `WRONG_DOMAIN`: a variable sort or bound changes the feasible solutions.
- `WRONG_TARGET`: the target expression does not match the requested quantity.
- `COMPUTATIONAL_ERROR`: the representation is faithful but its computed answer
  is wrong for a downstream computational reason.
- `OTHER`: an error not covered above, including a non-target-critical omission.
- `UNSURE`: temporary label only; it is forbidden in final analysis.

`target_critical_underformalization=true` is permitted only with
`MISSING_CONSTRAINT`. The annotator must give concise evidence for every error.
The manuscript must name both annotation models and the shared prompt hash and
describe the process as ``dual-model AI annotation with human adjudication and
audit.'' Report raw exact agreement, Cohen's kappa, and agreement on membership
in the primary subset before human resolution.

## Estimands

The primary subset is the adjudicated `MISSING_CONSTRAINT` cases. The primary
estimands are (i) ambiguity-detection recall and (ii) end-to-end grounded repair
success among this subset. Secondary estimands are conditional repair after
detection, detector precision, false ambiguity and false repair outside the
subset, and preservation of `CORRECT` controls. Each proportion receives a 95%
Wilson interval. Overall Structured Solver versus DeGro accuracy is paired by
problem and tested with an exact McNemar test; it is secondary because the
method is intentionally not designed for all error classes.

Do not call an ambiguous verdict a natural error without adjudication. Do not
count a numerically correct answer as a successful repair unless the accepted
grounded repair restores determinacy. Unsupported, inconsistent, and unknown
solver states remain coverage failures rather than incorrect detections.
