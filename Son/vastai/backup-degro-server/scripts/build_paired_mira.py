#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import random
import urllib.request
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from targetcheck import Constraint, ModelSpec, Variable, check_target_determinacy
from targetcheck.determinacy import CheckStatus


DATA_URL = "https://huggingface.co/datasets/samersaabjr/MIRA-MATH/resolve/main/family_types_20_50.jsonl"
DATA_SHA256 = "78a021526f9457af6e3776ac470c4ef1202d18fd9a19539e7e289294997b2ad0"
CODE_COMMIT = "72ff918901584d1d1e835a9f86d41e3d51a915a2"
FAMILIES = (
    "linear_system_separator",
    "graph_path_sums",
    "crt_reconstruction",
    "rankdef_linear_shared",
)


def expression(machine: dict[str, Any]) -> str:
    kind = machine["type"]
    if kind == "lin_eq":
        terms = [f"({coefficient}) * {name}" for name, coefficient in machine["coeffs"].items() if coefficient]
        return " + ".join(terms) + f" == {machine['rhs']}"
    if kind == "value":
        return f"{machine['var']} == {machine['value']}"
    if kind == "congruence":
        return f"{machine['var']} % {machine['mod']} == {machine['residue']}"
    raise ValueError(f"unsupported MIRA constraint type: {kind}")


def source_sentence(text: str) -> str:
    text = text.strip()
    return text if text.endswith(".") else text + "."


def spec_dict(spec: ModelSpec) -> dict[str, Any]:
    return {
        "variables": [v.__dict__ for v in spec.variables],
        "constraints": [c.__dict__ for c in spec.constraints],
        "target": spec.target,
        "metadata": spec.metadata,
    }


def convert(row: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]] | None:
    view_a = next(v["private_data"] for v in row["agent_views"] if v["agent_id"] == "A")
    view_b = next(v["private_data"] for v in row["agent_views"] if v["agent_id"] == "B")
    hint = row["minimal_hint_spec"]["atomic_hints"][0]
    range_bounds = row["global_metadata"].get("range")
    variables = tuple(
        Variable(
            name,
            "Int",
            lower=range_bounds[0] if range_bounds and name == row["global_metadata"].get("variable") else None,
            upper=range_bounds[1] if range_bounds and name == row["global_metadata"].get("variable") else None,
        )
        for name in view_a["unknowns"]
    )
    base_constraints = tuple(
        Constraint(f"c{i+1}", expression(machine), source_sentence(text), "EXPLICIT_TEXT")
        for i, (machine, text) in enumerate(zip(view_a["constraints_machine"], view_a["constraints_text"]))
    )
    missing_machine = dict(hint)
    missing_machine.pop("hint_id", None)
    missing_machine.pop("kind", None)
    missing_machine["type"] = hint["kind"]
    missing_text = next(
        text for machine, text in zip(view_b["constraints_machine"], view_b["constraints_text"])
        if machine["type"] == hint["kind"] and expression(machine) == expression(missing_machine)
    )
    missing = Constraint("c_missing", expression(missing_machine), source_sentence(missing_text), "EXPLICIT_TEXT")

    chosen: tuple[str, ModelSpec, int] | None = None
    for target in view_a["unknowns"]:
        if target not in row["global_solution"]:
            continue
        base = ModelSpec(variables, base_constraints, target, {"mira_id": row["id"], "family": row["family"]})
        full = ModelSpec(variables, base_constraints + (missing,), target, base.metadata)
        under_result = check_target_determinacy(base)
        full_result = check_target_determinacy(full)
        if under_result.status == CheckStatus.AMBIGUOUS and full_result.status == CheckStatus.DETERMINATE:
            gold = row["global_solution"][target]
            if full_result.target_value == gold:
                chosen = (target, base, gold)
                break
    if chosen is None:
        return None
    target, base, gold = chosen
    common = " ".join(source_sentence(t) for t in view_a["constraints_text"])
    question = f"Find the integer value of {target}."
    omission_problem = f"{common} {missing.source_span} {question}"
    underspecified_problem = f"{common} {question}"
    shared = {
        "pair_id": row["id"], "family": row["family"], "difficulty": row["difficulty"],
        "spec": spec_dict(base), "gold_target": gold,
    }
    return (
        {**shared, "label": "OMISSION", "problem": omission_problem, "missing_constraint": missing.__dict__},
        {**shared, "label": "UNDERSPECIFIED", "problem": underspecified_problem, "missing_constraint": None},
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw", type=Path, default=Path("data/mira_raw/family_types_20_50.jsonl"))
    parser.add_argument("--out", type=Path, default=Path("data/paired/mira_pilot_80.jsonl"))
    parser.add_argument("--per-family", type=int, default=20)
    parser.add_argument("--seed", type=int, default=20270909)
    args = parser.parse_args()
    args.raw.parent.mkdir(parents=True, exist_ok=True)
    if not args.raw.exists():
        urllib.request.urlretrieve(DATA_URL, args.raw)
    digest = hashlib.sha256(args.raw.read_bytes()).hexdigest()
    if digest != DATA_SHA256:
        raise SystemExit(f"dataset checksum mismatch: {digest}")

    buckets: dict[str, list[tuple[dict[str, Any], dict[str, Any]]]] = defaultdict(list)
    for line in args.raw.read_text().splitlines():
        row = json.loads(line)
        if row["family"] in FAMILIES:
            converted = convert(row)
            if converted:
                buckets[row["family"]].append(converted)
    rng = random.Random(args.seed)
    selected = []
    for family in FAMILIES:
        rng.shuffle(buckets[family])
        if len(buckets[family]) < args.per_family:
            raise SystemExit(f"only {len(buckets[family])} valid pairs for {family}")
        selected.extend(buckets[family][: args.per_family])
    rng.shuffle(selected)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w") as stream:
        for pair in selected:
            for case in pair:
                stream.write(json.dumps(case, separators=(",", ":")) + "\n")
    manifest = {
        "source_url": DATA_URL, "source_sha256": digest, "source_code_commit": CODE_COMMIT,
        "source_license": "CC BY 4.0", "selection_seed": args.seed,
        "families": list(FAMILIES), "pairs_per_family": args.per_family,
        "pairs": len(selected), "cases": len(selected) * 2,
        "output_sha256": hashlib.sha256(args.out.read_bytes()).hexdigest(),
    }
    args.out.with_suffix(".manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps({**manifest, "family_counts": Counter(pair[0]["family"] for pair in selected)}, indent=2))


if __name__ == "__main__":
    main()
