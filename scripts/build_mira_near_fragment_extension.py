#!/usr/bin/env python3
"""Build solver-verified paired cases for the two near-fragment MIRA families."""
from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path

from targetcheck import Constraint, ModelSpec, Variable, check_target_determinacy
from targetcheck.determinacy import CheckStatus
from targetcheck.pilot import score

from build_paired_mira import CODE_COMMIT, DATA_SHA256, DATA_URL, expression, source_sentence, spec_dict


RAW = Path("data/mira_raw/family_types_20_50.jsonl")
OUT = Path("data/paired/mira_near_fragment_174.jsonl")
FAMILIES = ("laplace_grid", "geometry_coordinates")


class NotTargetCritical(ValueError):
    pass


def views(row: dict) -> tuple[dict, dict]:
    return tuple(next(v["private_data"] for v in row["agent_views"] if v["agent_id"] == agent) for agent in ("A", "B"))


def missing_constraint(row: dict, view_b: dict) -> Constraint:
    hint = dict(row["minimal_hint_spec"]["atomic_hints"][0])
    hint.pop("hint_id", None)
    hint.pop("providers", None)
    hint.pop("consumers", None)
    hint["type"] = hint.pop("kind")
    missing_expression = expression(hint)
    missing_text = next(
        text for machine, text in zip(view_b["constraints_machine"], view_b["constraints_text"], strict=True)
        if machine["type"] == hint["type"] and expression(machine) == missing_expression
    )
    return Constraint("c_missing", missing_expression, source_sentence(missing_text), "EXPLICIT_TEXT")


def base_constraints(view_a: dict) -> tuple[Constraint, ...]:
    return tuple(
        Constraint(f"c{i + 1}", expression(machine), source_sentence(text), "EXPLICIT_TEXT")
        for i, (machine, text) in enumerate(zip(view_a["constraints_machine"], view_a["constraints_text"], strict=True))
    )


def convert_laplace(row: dict) -> tuple[dict, dict]:
    view_a, view_b = views(row)
    variables = tuple(Variable(name, "Int") for name in view_a["unknowns"])
    target_cell = row["global_metadata"]["target_cell"]
    target = f"u_{target_cell[0]}_{target_cell[1]}"
    gold = row["global_solution"]["value"]
    missing = missing_constraint(row, view_b)
    constraints = base_constraints(view_a)
    return make_pair(row, variables, constraints, target, gold, missing, view_a["constraints_text"])


def convert_geometry(row: dict) -> tuple[dict, dict]:
    view_a, view_b = views(row)
    variables = tuple(Variable(name, "Real") for name in view_a["unknowns"])
    qx, qy = row["global_metadata"]["point_q"]
    # Distance is nonnegative, so uniqueness of its square is equivalent to
    # uniqueness of the Euclidean distance while remaining in the SMT fragment.
    target = f"(x - ({qx})) ** 2 + (y - ({qy})) ** 2"
    distance = row["global_solution"]["value"]
    gold = distance * distance
    missing = missing_constraint(row, view_b)
    constraints = tuple(
        Constraint(f"c{i + 1}", expression(machine), source_sentence(text), "EXPLICIT_TEXT")
        for i, (machine, text) in enumerate(zip(view_a["constraints_machine"], view_a["constraints_text"][:len(view_a["constraints_machine"])], strict=True))
    )
    return make_pair(row, variables, constraints, target, gold, missing, view_a["constraints_text"])


def make_pair(row, variables, constraints, target, gold, missing, source_texts):
    metadata = {"mira_id": row["id"], "family": row["family"], "target_representation": "squared_distance" if row["family"] == "geometry_coordinates" else "direct_cell"}
    base = ModelSpec(variables, constraints, target, metadata)
    under = check_target_determinacy(base)
    full = check_target_determinacy(ModelSpec(variables, constraints + (missing,), target, metadata))
    if under.status != CheckStatus.AMBIGUOUS:
        raise NotTargetCritical(f"base_{under.status}")
    if full.status != CheckStatus.DETERMINATE or full.target_value != gold:
        raise ValueError(f"{row['id']}: full is {full.status}/{full.target_value}, expected DETERMINATE/{gold}")
    common = " ".join(source_sentence(text) for text in source_texts)
    question = ("Find the value of the target grid cell." if row["family"] == "laplace_grid"
                else "Find the Euclidean distance from the intersection point P to Q.")
    shared = {"pair_id": row["id"], "family": row["family"], "difficulty": row["difficulty"],
              "spec": spec_dict(base), "gold_target": gold}
    omission = {**shared, "label": "OMISSION", "problem": f"{common} {missing.source_span} {question}",
                "missing_constraint": missing.__dict__}
    underspecified = {**shared, "label": "UNDERSPECIFIED", "problem": f"{common} {question}",
                      "missing_constraint": None}
    gold_output = {"decision": "ADD_CONSTRAINT", "source_span": missing.source_span, "constraint": missing.expression}
    if not score(omission, gold_output)["correct"] or not score(underspecified, {"decision": "ABSTAIN", "source_span": None, "constraint": None})["correct"]:
        raise ValueError(f"{row['id']}: gold action failed scorer")
    return omission, underspecified


def main() -> None:
    if hashlib.sha256(RAW.read_bytes()).hexdigest() != DATA_SHA256:
        raise SystemExit("MIRA source checksum mismatch")
    pairs = []
    exclusions = Counter()
    for row in map(json.loads, RAW.read_text().splitlines()):
        if row["family"] not in FAMILIES:
            continue
        try:
            pairs.append((convert_laplace if row["family"] == "laplace_grid" else convert_geometry)(row))
        except NotTargetCritical as exc:
            exclusions[f"{row['family']}:{exc}"] += 1
    content = "".join(json.dumps(case, separators=(",", ":")) + "\n" for pair in pairs for case in pair)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(content)
    manifest = {
        "study": "near-fragment MIRA-Math extension; separate from main MIRA-300",
        "source_url": DATA_URL, "source_sha256": DATA_SHA256, "source_code_commit": CODE_COMMIT,
        "source_license": "CC BY 4.0", "families": list(FAMILIES),
        "family_counts": dict(Counter(pair[0]["family"] for pair in pairs)),
        "source_pairs_considered": 210, "pairs": len(pairs), "cases": len(pairs) * 2,
        "exclusion_counts": dict(exclusions),
        "geometry_target": "squared Euclidean distance; uniqueness-equivalent to nonnegative Euclidean distance",
        "selection": "all source instances in the two named families; no outcome-based selection",
        "output_sha256": hashlib.sha256(content.encode()).hexdigest(),
    }
    OUT.with_suffix(".manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps(manifest, indent=2))
    if len(pairs) != 174 or sum(exclusions.values()) != 36:
        raise SystemExit("expected 174 validated pairs and 36 non-target-critical exclusions")


if __name__ == "__main__":
    main()
