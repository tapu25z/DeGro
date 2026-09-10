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
- Quantitative paper results: **not collected**. Do not replace dashes in `main.tex` until frozen analysis output exists.

## Immediate experiment checklist

1. Import MIRA-Math and document its license/revision hash.
2. Freeze compatible families and deterministic exclusion reasons.
3. Generate 80 validated pairs and save a dataset manifest hash.
4. Freeze repair prompts and JSON schemas before inspecting method comparisons.
5. Run Self-Review, NonUnique, TargetWitness, and TargetCheck on GPT-OSS 20B.
6. Compute paired confidence intervals and preregistered McNemar comparisons.
7. Apply the go/no-go threshold before scaling to 120B and Gemma 4 31B.
