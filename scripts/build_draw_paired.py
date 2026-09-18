#!/usr/bin/env python3
"""Build solver-verified DRAW-Paired candidates and a human-review packet.

This script deliberately does not emit a frozen benchmark.  The proposed source
span and its deletion must first be approved by a human with
``finalize_draw_paired.py``.
"""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import math
import re
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

from targetcheck import Constraint, ModelSpec, Variable, check_target_determinacy
from targetcheck.determinacy import CheckResult, CheckStatus
from targetcheck.expressions import ExpressionNormalizationError, normalize_expression


DEFAULT_SOURCE = Path("data/draw1k/draw1k.jsonl")
DEFAULT_OUT = Path("data/paired/draw_paired")
IDENTIFIER = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
QUESTION_CUES = re.compile(r"\b(find|what|how|determine|calculate|please)\b", re.IGNORECASE)
NUMBER_LITERAL = re.compile(r"(?<![A-Za-z0-9_.])(?:\d+(?:\.\d*)?|\.\d+)(?![A-Za-z0-9_.])")
TITLE_ABBREVIATION = re.compile(r"\b(?:Mr|Mrs|Ms|Dr|Prof|Sr|Jr)\.$", re.IGNORECASE)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    with path.open() as stream:
        for line_number, line in enumerate(stream, 1):
            if line.strip():
                try:
                    yield json.loads(line)
                except json.JSONDecodeError as exc:
                    raise ValueError(f"{path}:{line_number}: invalid JSON") from exc


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as stream:
        for row in rows:
            stream.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")


def variable_names(equations: list[str]) -> tuple[str, ...]:
    seen: dict[str, None] = {}
    for equation in equations:
        for name in IDENTIFIER.findall(equation):
            if name not in {"and", "or", "not", "True", "False"}:
                seen.setdefault(name, None)
    return tuple(seen)


def normalized_equations(equations: list[str], names: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(normalize_expression(eq.strip(), names) for eq in equations)


def spec_dict(spec: ModelSpec) -> dict[str, Any]:
    return {
        "variables": [v.__dict__ for v in spec.variables],
        "constraints": [c.__dict__ for c in spec.constraints],
        "target": spec.target,
        "metadata": spec.metadata,
    }


def _numeric(value: bool | int | str | float | None) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    if "/" in text:
        numerator, denominator = text.split("/", 1)
        return float(numerator) / float(denominator)
    try:
        return float(text)
    except ValueError:
        return None


def agrees_with_gold(result: CheckResult, solutions: list[Any]) -> bool:
    predicted = _numeric(result.target_value)
    if predicted is None:
        return False
    return any(
        (gold_value := _numeric(gold)) is not None
        and math.isclose(predicted, gold_value, rel_tol=1e-5, abs_tol=1e-4)
        for gold in solutions
    )


def _clause_spans(text: str) -> list[tuple[int, int]]:
    # DRAW uses periods as sentence separators, often with spaces on both sides.
    # Do not treat decimal points such as ``.70`` or ``0.05`` as boundaries.
    boundaries = []
    for index, character in enumerate(text):
        if character in "!?;":
            boundaries.append(index + 1)
        elif character == ".":
            previous_is_digit = index > 0 and text[index - 1].isdigit()
            next_is_digit = index + 1 < len(text) and text[index + 1].isdigit()
            leading_decimal = index + 1 < len(text) and text[index + 1].isdigit()
            title_abbreviation = TITLE_ABBREVIATION.search(text[: index + 1]) is not None
            if not (previous_is_digit and next_is_digit) and not leading_decimal and not title_abbreviation:
                boundaries.append(index + 1)
    spans = []
    cursor = 0
    for end in boundaries + [len(text)]:
        start = cursor
        cursor = end
        while start < end and text[start].isspace():
            start += 1
        while end > start and text[end - 1].isspace():
            end -= 1
        if start < end:
            spans.append((start, end))
    return spans or [(0, len(text))]


def _template_mapping(row: dict[str, Any]) -> tuple[dict[int, int], bool]:
    equations = list(row.get("gold_equations") or [])
    templates = list(row.get("gold_template") or [])
    alignments = list(row.get("alignment") or [])
    if len(equations) != len(templates) or not equations:
        return {index: index for index in range(min(len(equations), len(templates)))}, True

    literals = [
        [abs(float(value)) for value in NUMBER_LITERAL.findall(equation)]
        for equation in equations
    ]
    template_values: list[list[float]] = []
    for template in templates:
        values = []
        for alignment in alignments:
            coefficient = str(alignment.get("coeff", ""))
            value = alignment.get("Value")
            if coefficient and isinstance(value, (int, float)) and re.search(
                rf"\b{re.escape(coefficient)}\b", template
            ):
                values.append(abs(float(value)))
        template_values.append(values)

    def pair_score(equation_index: int, template_index: int) -> int:
        score = 0
        for value in template_values[template_index]:
            variants = (value, value / 100.0)
            if any(
                math.isclose(literal, variant, rel_tol=1e-5, abs_tol=1e-5)
                for literal in literals[equation_index]
                for variant in variants
            ):
                score += 1
        return score

    ranked = []
    for permutation in itertools.permutations(range(len(templates))):
        score = sum(pair_score(eq_index, template_index) for eq_index, template_index in enumerate(permutation))
        ranked.append((score, permutation))
    ranked.sort(key=lambda item: (-item[0], item[1]))
    best_score, best = ranked[0]
    ambiguous = best_score == 0 or (len(ranked) > 1 and ranked[1][0] == best_score)
    return dict(enumerate(best)), ambiguous


def _alignment_locations(
    row: dict[str, Any], equation_index: int
) -> tuple[list[int], list[tuple[int, int]], list[str]]:
    templates = row.get("gold_template") or []
    alignments = row.get("alignment") or []
    mapping, mapping_ambiguous = _template_mapping(row)
    template_index = mapping.get(equation_index)
    if template_index is None or template_index >= len(templates):
        return [], [], ["missing_gold_template"]
    template = templates[template_index]
    sentence_ids: list[int] = []
    locations: list[tuple[int, int]] = []
    for alignment in alignments:
        coefficient = str(alignment.get("coeff", ""))
        if coefficient and re.search(rf"\b{re.escape(coefficient)}\b", template):
            token_id = alignment.get("TokenId")
            sentence_id = alignment.get("SentenceId")
            if isinstance(sentence_id, int):
                sentence_ids.append(sentence_id)
                if isinstance(token_id, int):
                    locations.append((sentence_id, token_id))
    return (
        sorted(set(sentence_ids)),
        sorted(set(locations)),
        (["template_mapping_ambiguous"] if mapping_ambiguous else [])
        + ([] if sentence_ids else ["no_aligned_coefficient"]),
    )


def propose_source_span(row: dict[str, Any], equation_index: int) -> dict[str, Any]:
    problem = row["problem"]
    spans = _clause_spans(problem)
    sentence_ids, locations, flags = _alignment_locations(row, equation_index)
    valid_sentence_ids = [sentence_id for sentence_id in sentence_ids if 0 <= sentence_id < len(spans)]
    if len(valid_sentence_ids) != len(sentence_ids):
        flags.append("alignment_sentence_out_of_range")

    chosen: tuple[int, int] | None = None
    if len(valid_sentence_ids) == 1:
        chosen = spans[valid_sentence_ids[0]]
    elif len(valid_sentence_ids) > 1:
        flags.append("aligned_tokens_cross_clauses")

    for other_index in range(len(row.get("gold_equations") or [])):
        if other_index == equation_index:
            continue
        other_sentence_ids, _, _ = _alignment_locations(row, other_index)
        if set(valid_sentence_ids) & set(other_sentence_ids):
            flags.append("span_also_supports_retained_equation")

    if chosen is None:
        # A conservative fallback: expose the first declarative clause for review,
        # but flag it so it cannot silently masquerade as a trusted alignment.
        chosen = next((span for span in spans if not QUESTION_CUES.search(problem[slice(*span)])), spans[0])
        flags.append("fallback_clause")

    start, end = chosen
    source_span = problem[start:end]
    if QUESTION_CUES.search(source_span):
        flags.append("span_contains_question_cue")
    if len(spans) == 1:
        flags.append("single_clause_problem")

    underspecified = (problem[:start].rstrip() + " " + problem[end:].lstrip()).strip()
    underspecified = re.sub(r"\s+", " ", underspecified)
    return {
        "char_start": start,
        "char_end": end,
        "source_span": source_span,
        "underspecified_problem": underspecified,
        "alignment_sentence_ids": valid_sentence_ids,
        "alignment_locations": [list(location) for location in locations],
        "method": "gold_template_coefficient_sentence_alignment",
        "flags": sorted(set(flags)),
    }


def convert_row(row: dict[str, Any], timeout_ms: int = 5_000) -> tuple[dict[str, Any] | None, str]:
    equations = list(row.get("gold_equations") or [])
    if len(equations) < 2:
        return None, "fewer_than_two_equations"
    names = variable_names(equations)
    if len(names) < 2:
        return None, "fewer_than_two_variables"
    try:
        expressions = normalized_equations(equations, names)
    except ExpressionNormalizationError:
        return None, "normalization_error"

    variables = tuple(Variable(name, "Real") for name in names)
    constraints = tuple(
        Constraint(f"c{index + 1}", expression, provenance="EXPLICIT_TEXT")
        for index, expression in enumerate(expressions)
    )
    candidates: list[tuple[tuple[Any, ...], dict[str, Any]]] = []
    for target_index, target in enumerate(names):
        full = ModelSpec(variables, constraints, target, {"draw_id": row["unique_id"], "split": row["split"]})
        full_result = check_target_determinacy(full, timeout_ms=timeout_ms)
        if full_result.status != CheckStatus.DETERMINATE:
            continue
        if not agrees_with_gold(full_result, list(row.get("gold_solutions") or [])):
            continue
        for equation_index, missing in enumerate(constraints):
            base_constraints = constraints[:equation_index] + constraints[equation_index + 1 :]
            base = ModelSpec(variables, base_constraints, target, full.metadata)
            base_result = check_target_determinacy(base, timeout_ms=timeout_ms)
            if base_result.status != CheckStatus.AMBIGUOUS:
                continue
            proposal = propose_source_span(row, equation_index)
            candidate_id = f"draw-paired/{row['source_index']}/{equation_index + 1}/{target}"
            candidate = {
                "candidate_id": candidate_id,
                "source_id": row["unique_id"],
                "source_index": row["source_index"],
                "split": row["split"],
                "target": target,
                "gold_target": full_result.target_value,
                "original_problem": row["problem"],
                "gold_equations": equations,
                "normalized_equations": list(expressions),
                "removed_equation_index": equation_index,
                "missing_constraint": missing.__dict__,
                "base_spec": spec_dict(base),
                "solver_checks": {
                    "full_status": full_result.status,
                    "full_target_value": full_result.target_value,
                    "base_status": base_result.status,
                    "base_witness_1": base_result.witness_1,
                    "base_witness_2": base_result.witness_2,
                    "gold_solution_match": True,
                },
                "span_proposal": proposal,
            }
            rank = (bool(proposal["flags"]), len(proposal["flags"]), equation_index, target_index)
            candidates.append((rank, candidate))

    if not candidates:
        return None, "no_determinate_to_ambiguous_removal"
    return min(candidates, key=lambda item: item[0])[1], "eligible"


def review_row(candidate: dict[str, Any], priority_rank: int | None = None) -> dict[str, Any]:
    return {
        **candidate,
        "review_priority_rank": priority_rank,
        "review_pool": "PRIMARY_CLEAN" if not candidate["span_proposal"]["flags"] else "RESERVE_FLAGGED",
        "review": {
            "status": "PENDING",
            "reviewer": None,
            "source_span_exact": None,
            "underspecified_problem": None,
            "meaning_preserved_after_deletion": None,
            "notes": None,
        },
    }


def build(source: Path, out_dir: Path, timeout_ms: int = 5_000) -> dict[str, Any]:
    candidates: list[dict[str, Any]] = []
    reasons: Counter[str] = Counter()
    seen_source_indices: set[int] = set()
    input_rows = 0
    for row in read_jsonl(source):
        if row.get("split") not in {"train", "dev"}:
            continue
        input_rows += 1
        source_index = int(row["source_index"])
        if source_index in seen_source_indices:
            reasons["duplicate_source_index"] += 1
            continue
        seen_source_indices.add(source_index)
        candidate, reason = convert_row(row, timeout_ms=timeout_ms)
        reasons[reason] += 1
        if candidate is not None:
            candidates.append(candidate)

    candidates.sort(key=lambda row: (row["split"], row["source_index"]))
    candidate_path = out_dir / "candidates.jsonl"
    review_path = out_dir / "review_packet.jsonl"
    write_jsonl(candidate_path, candidates)
    review_candidates = sorted(
        candidates,
        key=lambda row: (
            bool(row["span_proposal"]["flags"]),
            len(row["span_proposal"]["flags"]),
            row["split"],
            row["source_index"],
        ),
    )
    write_jsonl(
        review_path,
        (review_row(candidate, rank) for rank, candidate in enumerate(review_candidates, 1)),
    )
    split_counts = Counter(row["split"] for row in candidates)
    clean_split_counts = Counter(
        row["split"] for row in candidates if not row["span_proposal"]["flags"]
    )
    flag_counts = Counter(
        flag for row in candidates for flag in row["span_proposal"]["flags"]
    )
    manifest = {
        "dataset_name": "DRAW-Paired",
        "stage": "CANDIDATES_AWAITING_HUMAN_REVIEW",
        "source_path": str(source),
        "source_sha256": sha256(source),
        "included_splits": ["train", "dev"],
        "input_rows": input_rows,
        "unique_source_rows": len(seen_source_indices),
        "candidate_pairs": len(candidates),
        "candidate_cases_if_all_approved": 2 * len(candidates),
        "clean_span_proposals": sum(not row["span_proposal"]["flags"] for row in candidates),
        "candidate_pairs_by_split": dict(sorted(split_counts.items())),
        "clean_span_proposals_by_split": dict(sorted(clean_split_counts.items())),
        "span_flag_counts": dict(sorted(flag_counts.items())),
        "filter_counts": dict(sorted(reasons.items())),
        "candidate_sha256": sha256(candidate_path),
        "review_packet_sha256": sha256(review_path),
        "human_review_complete": False,
        "frozen": False,
    }
    manifest_path = out_dir / "candidate_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--timeout-ms", type=int, default=5_000)
    args = parser.parse_args()
    manifest = build(args.source, args.out_dir, timeout_ms=args.timeout_ms)
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
