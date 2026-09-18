"""Paired, pair-clustered comparison of fresh thinking on/off runs."""
from collections import Counter
import json
from pathlib import Path
import random
import statistics
import hashlib

from targetcheck.pilot import score, prompt_hash

RUN = Path("results/nano_thinking_ablation")
METHODS = ("self_review", "grounded_self_review", "nonunique", "nonunique_grounding")


def paired_ci(values, seed=42, samples=10000):
    rng = random.Random(seed)
    n = len(values)
    estimates = sorted(sum(rng.choices(values, k=n)) / n for _ in range(samples))
    return [estimates[int((samples - 1) * q)] * 100 for q in (.025, .975)]


def pair_randomization_p(values):
    """Exact two-sided paired sign-flip test, flipping whole pairs."""
    weights = [abs(value) for value in values if value]
    observed = abs(sum(values))
    distribution = {0: 1.0}
    for weight in weights:
        updated = {}
        for total, probability in distribution.items():
            for sign in (-1, 1):
                key = total + sign * weight
                updated[key] = updated.get(key, 0) + probability / 2
        distribution = updated
    return min(1.0, sum(p for value, p in distribution.items() if abs(value) >= observed))


def main():
    rows = {mode: [json.loads(line) for line in (RUN / f"nano_thinking_{mode}_complete.jsonl").read_text().splitlines()]
            for mode in ("on", "off")}
    lookup = {}
    for mode, records in rows.items():
        assert len(records) == 2400
        assert all(r["status"] == "ok" and r["think"] is (mode == "on") for r in records)
        lookup[mode] = {(r["pair_id"], r["label"], r["method"]): r for r in records}
        assert len(lookup[mode]) == 2400
    assert set(lookup["on"]) == set(lookup["off"])
    manifest = json.loads((RUN / "manifest.json").read_text())
    data_bytes = (RUN / "mira300_frozen.jsonl").read_bytes()
    assert hashlib.sha256(data_bytes).hexdigest() == manifest["data_sha256"]
    assert prompt_hash() == manifest["prompt_hash"]
    cases = {(r["pair_id"], r["label"]): r for line in data_bytes.decode().splitlines() if (r := json.loads(line))}
    for records in rows.values():
        for record in records:
            assert record["prompt_hash"] == manifest["prompt_hash"]
            assert record["temperature"] == 1.0 and record["model"] == manifest["model"]
            assert record["score"] == score(cases[(record["pair_id"], record["label"])], record["output"]), "Stored score changed"
    pair_ids = sorted({key[0] for key in lookup["on"]})
    assert len(pair_ids) == 300
    report = {"pairs": 300, "fresh_runs": True, "temperature": 1.0, "methods": {},
              "audit": {"rescored_records": 4800, "changed_scores": 0, "data_hash_verified": True,
                        "prompt_hash_verified": True}}
    attempts = {mode: [json.loads(line) for path in sorted((RUN / "raw").glob(f"{mode}_*.jsonl"), key=lambda p: ("_n" in p.name, p.name))
                       for line in path.read_text().splitlines()] for mode in ("on", "off")}
    for method in METHODS:
        result = {}
        for mode in ("on", "off"):
            selected = [r for r in rows[mode] if r["method"] == method]
            omissions = [r for r in selected if r["label"] == "OMISSION"]
            underspecified = [r for r in selected if r["label"] == "UNDERSPECIFIED"]
            adds = [r for r in selected if r["score"]["is_add"]]
            first_attempts = {}
            method_attempts = [r for r in attempts[mode] if r["method"] == method]
            for r in method_attempts:
                first_attempts.setdefault((r["pair_id"], r["label"]), r)
            result[mode] = {
                "FDA": 100 * sum(r["score"]["correct"] for r in selected) / 600,
                "RSR": 100 * sum(r["score"]["correct_repair"] for r in omissions) / 300,
                "CAR": 100 * sum(r["score"]["is_abstain"] for r in underspecified) / 300,
                "UR": 100 * sum(r["score"]["unsupported_repair"] for r in adds) / len(adds) if adds else None,
                "omission_abstains": sum(r["score"]["is_abstain"] for r in omissions),
                "omission_invalid_adds": sum(r["score"]["is_add"] and not r["score"]["correct_repair"] for r in omissions),
                "underspecified_adds": sum(r["score"]["is_add"] for r in underspecified),
                "unsupported_adds": sum(r["score"]["unsupported_repair"] for r in adds),
                "total_adds": len(adds),
                "median_eval_count": statistics.median(r["eval_count"] for r in selected if "eval_count" in r),
                "median_wall_seconds": statistics.median(r["wall_seconds"] for r in selected),
                "thinking_nonempty_cases": sum(r.get("thinking_chars", 0) > 0 for r in selected),
                "total_attempts": len(method_attempts),
                "first_attempt_errors": dict(Counter(r.get("error_type") for r in first_attempts.values() if r["status"] != "ok")),
                "first_attempt_FDA_counting_errors_as_wrong": 100 * sum(r.get("score", {}).get("correct", False) for r in first_attempts.values()) / 600,
                "family_RSR": {family: 100 * sum(r["score"]["correct_repair"] for r in omissions if r["family"] == family) /
                               sum(r["family"] == family for r in omissions) for family in sorted({r["family"] for r in omissions})},
            }
        for metric, labels, field in (("FDA", ("OMISSION", "UNDERSPECIFIED"), "correct"),
                                      ("RSR", ("OMISSION",), "correct_repair"),
                                      ("CAR", ("UNDERSPECIFIED",), "is_abstain")):
            differences = [sum(int(lookup["on"][(pid, label, method)]["score"][field]) -
                               int(lookup["off"][(pid, label, method)]["score"][field])
                               for label in labels) for pid in pair_ids]
            transitions = Counter((lookup["on"][(pid, label, method)]["score"][field],
                                   lookup["off"][(pid, label, method)]["score"][field])
                                  for pid in pair_ids for label in labels)
            result[f"{metric}_on_minus_off"] = {
                "delta_pp": 100 * sum(differences) / (300 * len(labels)),
                "pair_cluster_ci95_pp": paired_ci([value / len(labels) for value in differences]),
                "exact_pair_randomization_p": pair_randomization_p(differences),
                "on_only_correct": transitions[(True, False)], "off_only_correct": transitions[(False, True)],
            }
        report["methods"][method] = result
    ranked = sorted(METHODS, key=lambda m: report["methods"][m]["FDA_on_minus_off"]["exact_pair_randomization_p"])
    running = 0
    for index, method in enumerate(ranked):
        comparison = report["methods"][method]["FDA_on_minus_off"]
        running = max(running, min(1.0, (len(METHODS) - index) * comparison["exact_pair_randomization_p"]))
        comparison["holm_p_across_four_methods"] = running
    report["caveats"] = ["Single stochastic run per mode; no claim about multi-run variance.",
                          "Primary metrics use the first valid response with bounded retries, matching the existing main-run policy; first-attempt errors and FDA are also reported.",
                          "Unfinished jobs were re-sharded after latency imbalance; interrupted requests and service rate limits are documented in scheduling_notes.md. Wall latency and first-attempt service errors are descriptive, not controlled speed/robustness benchmarks.",
                          "FDA inference clusters both labels within each pair.",
                          "Four FDA comparisons receive Holm correction; RSR/CAR are diagnostic.",
                          "Main paper results are unchanged."]
    (RUN / "comparison.json").write_text(json.dumps(report, indent=2) + "\n")
    lines = ["# Nano thinking on/off: MIRA-300", "", "Fresh runs, temperature 1.0; same frozen 300 pairs, four methods and scorer.", "",
             "| Method | FDA on | FDA off | RSR on | RSR off | CAR on | CAR off | FDA delta on−off (95% pair CI) |", "|---|---:|---:|---:|---:|---:|---:|---|"]
    for method, result in report["methods"].items():
        a, b, delta = result["on"], result["off"], result["FDA_on_minus_off"]
        lo, hi = delta["pair_cluster_ci95_pp"]
        lines.append(f"| {method} | {a['FDA']:.1f} | {b['FDA']:.1f} | {a['RSR']:.1f} | {b['RSR']:.1f} | {a['CAR']:.1f} | {b['CAR']:.1f} | {delta['delta_pp']:+.1f} [{lo:+.1f}, {hi:+.1f}] |")
    lines += ["", "All rates are percentages; deltas are percentage points.", "",
              "## DeGro family-level repair success", "",
              "| Family | RSR thinking on | RSR thinking off |", "|---|---:|---:|"]
    degro = report["methods"]["nonunique_grounding"]
    for family, value in degro["on"]["family_RSR"].items():
        lines.append(f"| {family} | {value:.1f} | {degro['off']['family_RSR'][family]:.1f} |")
    lines += ["", "## DeGro errors and token usage", "",
              "| Measure | Thinking on | Thinking off |", "|---|---:|---:|"]
    for field in ("omission_abstains", "omission_invalid_adds", "underspecified_adds", "median_eval_count",
                  "thinking_nonempty_cases", "total_attempts", "first_attempt_FDA_counting_errors_as_wrong"):
        lines.append(f"| {field} | {degro['on'][field]} | {degro['off'][field]} |")
    lines += ["", "## Interpretation limits", "", *report["caveats"], "",
              "See comparison.json for UR, token counts, family-level RSR, paired transitions and corrected p-values."]
    (RUN / "comparison.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines), flush=True)


if __name__ == "__main__":
    main()
