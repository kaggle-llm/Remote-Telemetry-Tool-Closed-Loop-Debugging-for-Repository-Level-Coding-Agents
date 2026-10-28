"""Render the paired telemetry evaluation figure from the evaluation outputs."""

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parent
RESULTS = ROOT.parent / "eval" / "results"
SUMMARY = RESULTS / "ab_summary.json"
RUNS = RESULTS / "ab_runs.json"
OUTPUT = ROOT / "figure_ab_results.png"

INK = "#1e1b4b"
MUTED = "#334155"
CONDITION_A = "#94a3b8"
CONDITION_B = "#4f46e5"
GRID = "#e2e8f0"

WIDTH, HEIGHT = 10.4, 4.3
DPI = 220


def load():
    if not SUMMARY.is_file():
        raise SystemExit(f"Missing {SUMMARY}; run eval/eval_runner.py first.")
    summary = json.loads(SUMMARY.read_text(encoding="utf-8"))
    runs = []
    if RUNS.is_file():
        runs = json.loads(RUNS.read_text(encoding="utf-8")).get("runs", [])
    return summary, runs


def paired_deltas(runs):
    pairs = {}
    for run in runs:
        pairs.setdefault((run["task_id"], run["repeat"]), {})[run["condition"]] = run
    deltas = []
    for pair in pairs.values():
        if "A" in pair and "B" in pair:
            deltas.append(pair["B"]["total_tokens"] - pair["A"]["total_tokens"])
    return deltas


def outcome_counts(summary, key_a, key_b):
    total = summary["pairs"] or 1
    return summary[key_a] / total, summary[key_b] / total


def build(summary, runs):
    figure, axes = plt.subplots(1, 2, figsize=(WIDTH, HEIGHT), dpi=DPI, gridspec_kw={"width_ratios": [1.05, 1]})
    figure.patch.set_facecolor("white")

    left, right = axes
    labels = ["Repair (hidden test)", "Root cause (rubric)"]
    repair_a, repair_b = outcome_counts(summary, "resolution", "a_success"), None
    repair_a = summary["resolution"]["a_success"] / (summary["pairs"] or 1)
    repair_b = summary["resolution"]["b_success"] / (summary["pairs"] or 1)
    diagnosis_a = summary["diagnostic_accuracy"]["a_accurate"] / (summary["pairs"] or 1)
    diagnosis_b = summary["diagnostic_accuracy"]["b_accurate"] / (summary["pairs"] or 1)

    positions = [0, 1]
    height = 0.34
    left.barh(
        [position + height / 2 + 0.02 for position in positions],
        [repair_a, diagnosis_a],
        height=height,
        color=CONDITION_A,
        label="A: no diagnostic events",
        zorder=3,
    )
    left.barh(
        [position - height / 2 - 0.02 for position in positions],
        [repair_b, diagnosis_b],
        height=height,
        color=CONDITION_B,
        label="B: diagnostic events",
        zorder=3,
    )
    for position, values in ((0, (repair_a, repair_b)), (1, (diagnosis_a, diagnosis_b))):
        for offset, value in ((height / 2 + 0.02, values[0]), (-height / 2 - 0.02, values[1])):
            left.text(
                value + 0.015,
                position + offset,
                f"{value:.0%}",
                va="center",
                ha="left",
                fontsize=8.4,
                color=INK,
                zorder=4,
            )
    left.set_yticks(positions)
    left.set_yticklabels(labels, fontsize=9, color=INK)
    left.set_xlim(0, 1.18)
    left.set_xticks([0, 0.25, 0.5, 0.75, 1.0])
    left.set_xticklabels(["0", "25", "50", "75", "100%"], fontsize=8.2, color=MUTED)
    left.set_xlabel("paired trials", fontsize=8.6, color=MUTED)
    left.set_title(
        f"Outcome rate over {summary['pairs']} paired trials",
        fontsize=9.8,
        color=INK,
        weight="bold",
        loc="left",
        pad=8,
    )
    left.grid(axis="x", color=GRID, linewidth=0.8, zorder=0)
    left.set_axisbelow(True)
    for side in ("top", "right", "left"):
        left.spines[side].set_visible(False)
    left.spines["bottom"].set_color(GRID)
    left.legend(fontsize=8.2, frameon=False, loc="lower right", labelcolor=MUTED)

    deltas = paired_deltas(runs)
    tokens = summary["token_delta_b_minus_a"]
    if deltas:
        for index, delta in enumerate(deltas):
            right.scatter(
                delta,
                index + 0.5,
                s=26,
                color=CONDITION_B,
                alpha=0.75,
                edgecolor="white",
                linewidth=0.6,
                zorder=3,
            )
        right.axvline(0, color=MUTED, linewidth=1.0, linestyle=(0, (4, 3)), zorder=2)
        if tokens["mean"] is not None:
            right.axvspan(tokens["low"], tokens["high"], color=CONDITION_B, alpha=0.10, zorder=1)
            right.axvline(tokens["mean"], color=CONDITION_B, linewidth=1.6, zorder=4)
        right.set_ylim(0, len(deltas) + 1)
        right.set_yticks([])
        right.set_xlabel("tokens in B minus tokens in A", fontsize=8.6, color=MUTED)
        right.set_title(
            "Context cost per paired trial",
            fontsize=9.8,
            color=INK,
            weight="bold",
            loc="left",
            pad=8,
        )
        if tokens["mean"] is not None:
            right.text(
                0.98,
                0.94,
                f"mean {tokens['mean']:+.0f}\n95% CI {tokens['low']:+.0f} to {tokens['high']:+.0f}",
                transform=right.transAxes,
                ha="right",
                va="top",
                fontsize=8.4,
                color=INK,
                zorder=5,
            )
    else:
        right.text(
            0.5,
            0.5,
            "no paired runs recorded",
            transform=right.transAxes,
            ha="center",
            va="center",
            fontsize=9,
            color=MUTED,
        )
        right.set_axis_off()

    for axis in axes:
        axis.tick_params(colors=MUTED, labelsize=8.2)
    figure.suptitle(
        f"Paired evaluation on {summary.get('model', 'local model')}: task-scoped telemetry vs. none",
        fontsize=10.4,
        color=INK,
        weight="bold",
        x=0.012,
        ha="left",
        y=0.985,
    )
    figure.text(
        0.012,
        0.015,
        "Condition A and B share the prompt, tool surface, model and repository; only the case-scoped telemetry rows differ.",
        fontsize=7.8,
        color=MUTED,
        ha="left",
    )
    figure.tight_layout(rect=(0, 0.045, 1, 0.94))
    return figure, axes


def validate(figure, axes):
    figure.canvas.draw()
    renderer = figure.canvas.get_renderer()
    problems = []
    for axis in axes:
        for artist in axis.texts:
            extent = artist.get_window_extent(renderer=renderer)
            bounds = axis.get_window_extent(renderer=renderer)
            if extent.x1 > bounds.x1 + 1 or extent.x0 < bounds.x0 - 1:
                problems.append(f"text outside axes: {artist.get_text()!r}")
    return problems


def main():
    summary, runs = load()
    figure, axes = build(summary, runs)
    problems = validate(figure, axes)
    figure.savefig(OUTPUT, dpi=DPI, facecolor="white", bbox_inches="tight", pad_inches=0.12)
    plt.close(figure)
    print(f"Created {OUTPUT}")
    for problem in problems:
        print(f"LAYOUT WARNING: {problem}")
    if problems:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
