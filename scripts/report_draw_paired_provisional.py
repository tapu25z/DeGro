#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from pathlib import Path


DATA = Path("data/paired/draw_paired/draw_paired_provisional_300.jsonl")
MODELS = {
    "GPT-OSS 20B": "gpt_oss_20b",
    "GPT-OSS 120B": "gpt_oss_120b",
    "Nemotron Nano 30B": "nemotron_3_nano_30b",
}
BASELINE = "grounded_self_review"
DEGRO = "nonunique_grounding"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def holm(rows: list[dict]) -> None:
    ordered = sorted(range(len(rows)), key=lambda index: rows[index]["p_raw"])
    running = 0.0
    total = len(rows)
    for rank, index in enumerate(ordered):
        adjusted = min(1.0, (total - rank) * rows[index]["p_raw"])
        running = max(running, adjusted)
        rows[index]["p_holm_across_models"] = running


def main() -> None:
    case_count = len(DATA.read_text().splitlines())
    expected_count = case_count * 4
    model_rows = []
    output_hashes = {}
    for model_name, stem in MODELS.items():
        complete = Path(f"results/{stem}_draw_paired_provisional300_complete.jsonl")
        analysis_path = Path(f"results/{stem}_draw_paired_provisional300_analysis.json")
        records = [json.loads(line) for line in complete.read_text().splitlines()]
        if len(records) != expected_count:
            raise ValueError(f"{model_name}: expected {expected_count} records, found {len(records)}")
        keys = {(row["pair_id"], row["label"], row["method"]) for row in records}
        if len(keys) != expected_count or any(row.get("status") != "ok" for row in records):
            raise ValueError(f"{model_name}: output is not complete and unique")
        analysis = json.loads(analysis_path.read_text())
        comparison = next(
            row
            for row in analysis["decision_mcnemar"]
            if row["first"] == DEGRO and row["second"] == BASELINE
        )
        baseline = analysis["summary"][BASELINE]
        degro = analysis["summary"][DEGRO]
        model_rows.append(
            {
                "model": model_name,
                "records": len(records),
                "baseline": {
                    "RSR": baseline["RSR"]["estimate"],
                    "CAR": baseline["CAR"]["estimate"],
                    "FDA": baseline["FDA"]["estimate"],
                    "unsupported_rate_among_additions": baseline["Unsupported"]["rate"],
                },
                "degro": {
                    "RSR": degro["RSR"]["estimate"],
                    "CAR": degro["CAR"]["estimate"],
                    "FDA": degro["FDA"]["estimate"],
                    "unsupported_rate_among_additions": degro["Unsupported"]["rate"],
                },
                "fda_delta": comparison["delta"],
                "fda_delta_ci95": comparison["delta_ci95"],
                "first_only": comparison["first_only"],
                "second_only": comparison["second_only"],
                "p_raw": comparison["p_raw"],
            }
        )
        output_hashes[complete.name] = digest(complete)
    holm(model_rows)

    report = {
        "dataset_stage": "PROVISIONAL_AWAITING_HUMAN_REVIEW",
        "claim_scope": "exploratory/provisional until exact spans and deletions are human-approved",
        "dataset": str(DATA),
        "dataset_sha256": digest(DATA),
        "pairs": case_count // 2,
        "cases": case_count,
        "methods": ["self_review", BASELINE, "nonunique", DEGRO],
        "primary_comparison": f"{DEGRO} minus {BASELINE} on FDA",
        "multiplicity": "Holm correction across the three model-specific primary comparisons",
        "models": model_rows,
        "output_sha256": output_hashes,
    }
    json_path = Path("results/draw_paired_provisional300_report.json")
    md_path = Path("results/draw_paired_provisional300_report.md")
    json_path.write_text(json.dumps(report, indent=2) + "\n")

    lines = [
        f"# DRAW-Paired provisional cohort ({case_count // 2} retained pairs)",
        "",
        "> Provisional: exact source spans and deletions still require human approval.",
        "",
        "| Model | Method | RSR | CAR | FDA | Unsupported/additions |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for row in model_rows:
        for label, values in (("Grounded self-review", row["baseline"]), ("DeGro", row["degro"])):
            lines.append(
                f"| {row['model']} | {label} | {100*values['RSR']:.1f} | {100*values['CAR']:.1f} | "
                f"{100*values['FDA']:.1f} | {100*values['unsupported_rate_among_additions']:.1f} |"
            )
    lines.extend(["", "## Paired primary comparison", ""])
    for row in model_rows:
        low, high = row["fda_delta_ci95"]
        lines.append(
            f"- {row['model']}: {100*row['fda_delta']:+.1f} FDA points "
            f"(95% CI [{100*low:+.1f}, {100*high:+.1f}]); "
            f"McNemar p={row['p_raw']:.6g}, Holm p={row['p_holm_across_models']:.6g}."
        )
    md_path.write_text("\n".join(lines) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
