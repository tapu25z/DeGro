#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import random
from collections import defaultdict
from pathlib import Path


METRICS = {
    "RSR": ("OMISSION", "correct_repair"),
    "Semantic": ("OMISSION", "semantic_repair"),
    "Functional": ("OMISSION", "functional_repair"),
    "Grounded": ("OMISSION", "grounded_repair"),
    "CAR": ("UNDERSPECIFIED", "is_abstain"),
    "FDA": (None, "correct"),
    "ORR": ("UNDERSPECIFIED", "is_add"),
}
PLANNED_COMPARISONS = (
    ("H1", "RSR", "minimal_witness", "nonunique"),
    ("H2", "RSR", "minimal_witness", "random_pair"),
    ("H3", "CAR", "targetcheck", "target_witness"),
    ("H4", "FDA", "targetcheck", "nonunique_grounding"),
)
DECISION_COMPARISONS = (
    ("D1", "FDA", "grounded_self_review", "self_review"),
    ("D2", "FDA", "minimal_witness_grounding", "nonunique_grounding"),
    ("D3", "FDA", "minimal_witness_grounding", "minimal_witness"),
    ("D4", "FDA", "nonunique_grounding", "grounded_self_review"),
)


def rate(rows: list[dict], metric: str) -> float:
    label, field = METRICS[metric]
    selected = [row for row in rows if label is None or row["label"] == label]
    return sum(bool(row["score"][field]) for row in selected) / len(selected)


def percentile(values: list[float], probability: float) -> float:
    ordered = sorted(values)
    index = probability * (len(ordered) - 1)
    lower = math.floor(index)
    upper = math.ceil(index)
    if lower == upper:
        return ordered[lower]
    return ordered[lower] * (upper - index) + ordered[upper] * (index - lower)


def cluster_bootstrap_ci(rows: list[dict], metric: str, samples: int, seed: int) -> tuple[float, float]:
    by_pair: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        by_pair[row["pair_id"]].append(row)
    pair_ids = sorted(by_pair)
    rng = random.Random(seed)
    estimates = []
    for _ in range(samples):
        sampled = [rng.choice(pair_ids) for _ in pair_ids]
        sample_rows = [row for pair_id in sampled for row in by_pair[pair_id]]
        estimates.append(rate(sample_rows, metric))
    return percentile(estimates, 0.025), percentile(estimates, 0.975)


def exact_binomial_two_sided(successes: int, trials: int) -> float:
    if trials == 0:
        return 1.0
    probabilities = [math.comb(trials, k) * (0.5**trials) for k in range(trials + 1)]
    observed = probabilities[successes]
    return min(1.0, sum(value for value in probabilities if value <= observed + 1e-15))


def mcnemar(rows: list[dict], metric: str, first: str, second: str) -> dict:
    label, field = METRICS[metric]
    lookup = {
        (row["pair_id"], row["label"], row["method"]): bool(row["score"][field])
        for row in rows
        if label is None or row["label"] == label
    }
    cases = sorted({(pair_id, case_label) for pair_id, case_label, _ in lookup})
    first_only = sum(
        lookup[(pair_id, case_label, first)] and not lookup[(pair_id, case_label, second)]
        for pair_id, case_label in cases
    )
    second_only = sum(
        lookup[(pair_id, case_label, second)] and not lookup[(pair_id, case_label, first)]
        for pair_id, case_label in cases
    )
    discordant = first_only + second_only
    return {
        "first_only": first_only,
        "second_only": second_only,
        "delta": (first_only - second_only) / len(cases),
        "p_raw": exact_binomial_two_sided(min(first_only, second_only), discordant),
    }


def holm_adjust(results: list[dict]) -> None:
    ordered = sorted(enumerate(results), key=lambda item: item[1]["p_raw"])
    running = 0.0
    count = len(results)
    for rank, (index, result) in enumerate(ordered):
        adjusted = min(1.0, (count - rank) * result["p_raw"])
        running = max(running, adjusted)
        results[index]["p_holm"] = running


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("paths", type=Path, nargs="+")
    parser.add_argument("--bootstrap-samples", type=int, default=10_000)
    parser.add_argument("--seed", type=int, default=20270910)
    args = parser.parse_args()
    rows = [
        json.loads(line)
        for path in args.paths
        for line in path.read_text().splitlines()
    ]
    rows = [row for row in rows if row.get("status") == "ok"]
    methods = sorted({row["method"] for row in rows})

    summary = {}
    for method in methods:
        method_rows = [row for row in rows if row["method"] == method]
        summary[method] = {}
        for offset, metric in enumerate(METRICS):
            estimate = rate(method_rows, metric)
            low, high = cluster_bootstrap_ci(
                method_rows, metric, args.bootstrap_samples, args.seed + offset
            )
            summary[method][metric] = {"estimate": estimate, "ci95": [low, high]}
        additions = [row for row in method_rows if row["score"]["is_add"]]
        unsupported = sum(row["score"]["unsupported_repair"] for row in additions)
        summary[method]["Unsupported"] = {
            "count": unsupported,
            "additions": len(additions),
            "rate": unsupported / len(additions) if additions else 0.0,
        }

    comparisons = []
    skipped_comparisons = []
    for hypothesis, metric, first, second in PLANNED_COMPARISONS:
        if first not in methods or second not in methods:
            skipped_comparisons.append({
                "hypothesis": hypothesis,
                "metric": metric,
                "first": first,
                "second": second,
                "reason": "method absent from this run",
            })
            continue
        result = {"hypothesis": hypothesis, "metric": metric, "first": first, "second": second}
        result.update(mcnemar(rows, metric, first, second))
        comparisons.append(result)
    holm_adjust(comparisons)

    decision_comparisons = []
    for hypothesis, metric, first, second in DECISION_COMPARISONS:
        if first not in methods or second not in methods:
            continue
        result = {"hypothesis": hypothesis, "metric": metric, "first": first, "second": second}
        result.update(mcnemar(rows, metric, first, second))
        decision_comparisons.append(result)
    holm_adjust(decision_comparisons)

    by_family = {}
    for family in sorted({row["family"] for row in rows}):
        family_rows = [row for row in rows if row["family"] == family]
        by_family[family] = {
            method: {
                "RSR": rate([row for row in family_rows if row["method"] == method], "RSR"),
                "CAR": rate([row for row in family_rows if row["method"] == method], "CAR"),
                "FDA": rate([row for row in family_rows if row["method"] == method], "FDA"),
            }
            for method in methods
        }

    print(json.dumps({
        "records": len(rows),
        "methods": methods,
        "summary": summary,
        "planned_mcnemar": comparisons,
        "decision_mcnemar": decision_comparisons,
        "skipped_comparisons": skipped_comparisons,
        "by_family": by_family,
    }, indent=2))


if __name__ == "__main__":
    main()
