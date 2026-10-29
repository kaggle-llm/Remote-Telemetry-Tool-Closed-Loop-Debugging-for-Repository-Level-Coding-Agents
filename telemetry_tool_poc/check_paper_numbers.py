"""Check that every evaluation number quoted in the paper matches the stored runs.

The draft is the submitted artifact, so a stale or mistyped number is a silent
correctness bug. This script re-reads the two paired-evaluation summaries and
verifies the table rows, the p-values, the token deltas and the pair counts
that the paper quotes, and it fails when the draft still carries numbers from
an earlier run.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent
DRAFT = ROOT / "PAPER_DRAFT.md"
SUMMARIES = {
    "compact": REPO / "eval" / "results" / "ab_summary.json",
    "larger": REPO / "eval" / "results_large" / "ab_summary.json",
}
MINUS = "\u2212"


def load_summary(name):
    path = SUMMARIES[name]
    if not path.is_file():
        raise SystemExit(f"Missing {path}; run eval/eval_runner.py first.")
    return json.loads(path.read_text(encoding="utf-8"))


def signed(value):
    return f"{MINUS}{abs(value):,.0f}" if value < 0 else f"{value:,.0f}"


def table_row(text, label):
    match = re.search(rf"^\|\s*{re.escape(label)}\s*\|(.+)\|\s*$", text, flags=re.M)
    if not match:
        raise SystemExit(f"Draft table row not found: {label}")
    return [cell.strip() for cell in match.group(1).split("|")]


def main():
    text = DRAFT.read_text(encoding="utf-8")
    summaries = {name: load_summary(name) for name in SUMMARIES}
    compact, larger = summaries["compact"], summaries["larger"]
    pairs = compact["pairs"]
    failures = []

    if compact["pairs"] != larger["pairs"]:
        failures.append(f"variants have different pair counts: {compact['pairs']} and {larger['pairs']}")
    if compact["repeats"] != larger["repeats"]:
        failures.append("variants have different repeat counts")
    if compact["model"] != larger["model"]:
        failures.append("variants were run with different models")
    if compact["seed"] != larger["seed"]:
        failures.append("variants were run with different seeds")

    expected_rows = {
        "Validation test passed": lambda s: [f"{s['resolution']['a_success']}/{s['pairs']}", f"{s['resolution']['b_success']}/{s['pairs']}"],
        "Root cause matched rubric": lambda s: [f"{s['diagnostic_accuracy']['a_accurate']}/{s['pairs']}", f"{s['diagnostic_accuracy']['b_accurate']}/{s['pairs']}"],
        "Named the responsible module": lambda s: [f"{s['localization']['a_mentioned']}/{s['pairs']}", f"{s['localization']['b_mentioned']}/{s['pairs']}"],
    }
    for label, build in expected_rows.items():
        row = table_row(text, label)
        expected = build(compact) + build(larger)
        if row != expected:
            failures.append(f"table row '{label}': draft {row} != runs {expected}")

    fetch_row = table_row(text, "Telemetry fetches / file edits")
    expected_fetch = []
    for summary in (compact, larger):
        expected_fetch.append(f"{summary['telemetry_fetches']['a']} / {summary['edits']['a']}")
        expected_fetch.append(f"{summary['telemetry_fetches']['b']} / {summary['edits']['b']}")
    if fetch_row != expected_fetch:
        failures.append(f"table row 'Telemetry fetches / file edits': draft {fetch_row} != runs {expected_fetch}")

    header = re.search(r"^\|\s*Outcome \((\d+) pairs per variant\)\s*\|", text, flags=re.M)
    if not header:
        failures.append("results table header not found")
    elif int(header.group(1)) != pairs:
        failures.append(f"table header says {header.group(1)} pairs per variant, runs have {pairs}")

    total = re.search(r"giving (\d+) paired trials per variant \((\d+) in total\)", text)
    if not total:
        failures.append("paired trial count sentence not found")
    elif (int(total.group(1)), int(total.group(2))) != (pairs, 2 * pairs):
        failures.append(f"paired trial sentence says {total.groups()}, runs have {pairs} pairs and {2 * pairs} trials")

    abstract = re.search(r"Across (\d+) paired trials", text)
    if not abstract:
        failures.append("abstract trial count not found")
    elif int(abstract.group(1)) != 2 * pairs:
        failures.append(f"abstract says {abstract.group(1)} trials, runs have {2 * pairs}")

    diagnostic = re.search(
        r"compact (\d+/\d+) against (\d+/\d+), p = ([\d.]+); larger (\d+/\d+) against (\d+/\d+), p = ([\d.]+)",
        text,
    )
    if not diagnostic:
        failures.append("diagnostic accuracy sentence not found")
    else:
        c_a, c_b, c_p, l_a, l_b, l_p = diagnostic.groups()
        expected_c = (
            f"{compact['diagnostic_accuracy']['b_accurate']}/{pairs}",
            f"{compact['diagnostic_accuracy']['a_accurate']}/{pairs}",
            f"{compact['diagnostic_accuracy']['mcnemar_exact_p']:.3f}",
            f"{larger['diagnostic_accuracy']['b_accurate']}/{pairs}",
            f"{larger['diagnostic_accuracy']['a_accurate']}/{pairs}",
            f"{larger['diagnostic_accuracy']['mcnemar_exact_p']:.3f}",
        )
        if (c_a, c_b, c_p, l_a, l_b, l_p) != expected_c:
            failures.append(f"diagnostic sentence: draft {(c_a, c_b, c_p, l_a, l_b, l_p)} != runs {expected_c}")

    localization = re.search(r"localization was indistinguishable \(p = ([\d.]+) in both\)", text)
    if not localization:
        failures.append("localization p-values not found")
    else:
        expected_p = (
            f"{compact['localization']['mcnemar_exact_p']:.3f}",
            f"{larger['localization']['mcnemar_exact_p']:.3f}",
        )
        if localization.group(1) not in expected_p:
            failures.append(f"localization p-value: draft {localization.group(1)} != runs {sorted(expected_p)}")

    resolution = re.search(r"exact McNemar p = ([\d.]+) for the compact and ([\d.]+) for the larger", text)
    if not resolution:
        failures.append("resolution p-values not found")
    else:
        expected_p = (
            f"{compact['resolution']['mcnemar_exact_p']:.3f}",
            f"{larger['resolution']['mcnemar_exact_p']:.3f}",
        )
        if resolution.groups() != expected_p:
            failures.append(f"resolution p-values: draft {resolution.groups()} != runs {expected_p}")

    tokens = re.search(
        r"was (−?[\d,]+) in the compact variant \(95% bootstrap CI (−?[\d,]+) to (−?[\d,]+)\) and (−?[\d,]+) in the larger one \((−?[\d,]+) to (−?[\d,]+)\)",
        text,
    )
    if not tokens:
        failures.append("token delta sentence not found")
    else:
        c_mean, c_low, c_high, l_mean, l_low, l_high = tokens.groups()
        expected_tokens = (
            signed(compact["token_delta_b_minus_a"]["mean"]),
            signed(compact["token_delta_b_minus_a"]["low"]),
            signed(compact["token_delta_b_minus_a"]["high"]),
            signed(larger["token_delta_b_minus_a"]["mean"]),
            signed(larger["token_delta_b_minus_a"]["low"]),
            signed(larger["token_delta_b_minus_a"]["high"]),
        )
        if (c_mean, c_low, c_high, l_mean, l_low, l_high) != expected_tokens:
            failures.append(f"token sentence: draft {tokens.groups()} != runs {expected_tokens}")

    for stale in (r"\b18 pairs\b", r"\b36 paired trials\b", r"18/18", r"\brepeats 3\b", r"\b3 repeats each\b"):
        if re.search(stale, text):
            failures.append(f"stale value still in the draft: {stale}")

    if failures:
        for failure in failures:
            print(f"MISMATCH: {failure}")
        return 1
    print(f"Paper numbers match the stored runs ({pairs} pairs per variant, {2 * pairs} trials).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
