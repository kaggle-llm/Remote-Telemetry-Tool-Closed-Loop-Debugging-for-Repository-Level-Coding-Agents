"""Render the paired telemetry evaluation figure from the evaluation outputs.

The figure compares condition A (no diagnostic events) with condition B
(diagnostic events) for each repository variant: the compact application and
the larger application with more plausible candidate modules.
"""

import argparse
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parent
RESULTS = ROOT.parent / "eval" / "results"
RESULTS_LARGE = ROOT.parent / "eval" / "results_large"
SUMMARY = RESULTS / "ab_summary.json"
RUNS = RESULTS / "ab_runs.json"
SUMMARY_LARGE = RESULTS_LARGE / "ab_summary.json"
RUNS_LARGE = RESULTS_LARGE / "ab_runs.json"
OUTPUT = ROOT / "figure_ab_results.png"

INK = "#1e1b4b"
MUTED = "#334155"
CONDITION_A = "#94a3b8"
CONDITION_B = "#4f46e5"
GRID = "#e2e8f0"

WIDTH, HEIGHT = 12.6, 4.1
DPI = 220


def load(summary_path, runs_path):
    if not summary_path.is_file():
        return None, []
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    runs = []
    if runs_path.is_file():
        runs = json.loads(runs_path.read_text(encoding="utf-8")).get("runs", [])
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


def outcome_panel(axis, summary, title):
    total = summary["pairs"] or 1
    repair_a = summary["resolution"]["a_success"] / total
    repair_b = summary["resolution"]["b_success"] / total
    diagnosis_a = summary["diagnostic_accuracy"]["a_accurate"] / total
    diagnosis_b = summary["diagnostic_accuracy"]["b_accurate"] / total
    labels = ["Repair (hidden test)", "Root cause (rubric)"]
    positions = [0, 1]
    height = 0.34
    axis.barh(
        [position + height / 2 + 0.02 for position in positions],
        [repair_a, diagnosis_a],
        height=height,
        color=CONDITION_A,
        label="A: no diagnostic events",
        zorder=3,
    )
    axis.barh(
        [position - height / 2 - 0.02 for position in positions],
        [repair_b, diagnosis_b],
        height=height,
        color=CONDITION_B,
        label="B: diagnostic events",
        zorder=3,
    )
    for position, values in ((0, (repair_a, repair_b)), (1, (diagnosis_a, diagnosis_b))):
        for offset, value in ((height / 2 + 0.02, values[0]), (-height / 2 - 0.02, values[1])):
            axis.text(
                value + 0.015,
                position + offset,
                f"{value:.0%}",
                va="center",
                ha="left",
                fontsize=8.2,
                color=INK,
                zorder=4,
            )
    axis.set_yticks(positions)
    axis.set_yticklabels(labels, fontsize=8.8, color=INK)
    axis.set_xlim(0, 1.2)
    axis.set_xticks([0, 0.25, 0.5, 0.75, 1.0])
    axis.set_xticklabels(["0", "25", "50", "75", "100%"], fontsize=8.0, color=MUTED)
    axis.set_xlabel("paired trials", fontsize=8.4, color=MUTED)
    axis.set_title(title, fontsize=9.6, color=INK, weight="bold", loc="left", pad=8)
    axis.grid(axis="x", color=GRID, linewidth=0.8, zorder=0)
    axis.set_axisbelow(True)
    for side in ("top", "right", "left"):
        axis.spines[side].set_visible(False)
    axis.spines["bottom"].set_color(GRID)


def token_panel(axis, entries):
    offset = 0.0
    labels = []
    for title, summary, runs in entries:
        deltas = paired_deltas(runs)
        tokens = summary["token_delta_b_minus_a"]
        if not deltas:
            continue
        for index, delta in enumerate(deltas):
            axis.scatter(
                delta,
                index + offset,
                s=24,
                color=CONDITION_B,
                alpha=0.7,
                edgecolor="white",
                linewidth=0.5,
                zorder=3,
            )
        axis.axvline(0, color=MUTED, linewidth=1.0, linestyle=(0, (4, 3)), zorder=2)
        if tokens["mean"] is not None:
            axis.axvspan(tokens["low"], tokens["high"], color=CONDITION_B, alpha=0.08, zorder=1)
            axis.axvline(tokens["mean"], color=CONDITION_B, linewidth=1.5, zorder=4)
        labels.append((index + offset, title))
        offset += len(deltas) + 1.5
    if not labels:
        axis.text(0.5, 0.5, "no paired runs recorded", transform=axis.transAxes, ha="center", va="center", fontsize=9, color=MUTED)
        axis.set_axis_off()
        return
    axis.set_yticks([position for position, _ in labels])
    axis.set_yticklabels([title for _, title in labels], fontsize=8.4, color=MUTED)
    axis.set_ylim(-1, offset)
    axis.set_xlabel("tokens in B minus tokens in A", fontsize=8.4, color=MUTED)
    axis.set_title("Context cost per paired trial", fontsize=9.6, color=INK, weight="bold", loc="left", pad=8)
    axis.grid(axis="x", color=GRID, linewidth=0.8, zorder=0)
    axis.set_axisbelow(True)
    for side in ("top", "right", "left"):
        axis.spines[side].set_visible(False)
    axis.spines["bottom"].set_color(GRID)


def build(small, large):
    figure, axes = plt.subplots(1, 3, figsize=(WIDTH, HEIGHT), dpi=DPI)
    figure.patch.set_facecolor("white")

    small_summary, small_runs = small
    large_summary, large_runs = large

    outcome_panel(
        axes[0],
        small_summary,
        f"Compact repository ({small_summary['pairs']} paired trials)",
    )
    if large_summary:
        outcome_panel(
            axes[1],
            large_summary,
            f"Larger repository ({large_summary['pairs']} paired trials)",
        )
        entries = [("compact", small_summary, small_runs), ("larger", large_summary, large_runs)]
    else:
        axes[1].axis("off")
        entries = [("compact", small_summary, small_runs)]
    token_panel(axes[2], entries)

    handles, labels = axes[0].get_legend_handles_labels()
    figure.legend(
        handles,
        labels,
        loc="upper left",
        bbox_to_anchor=(0.008, 0.930),
        bbox_transform=figure.transFigure,
        ncol=2,
        frameon=False,
        fontsize=8.2,
        labelcolor=MUTED,
        handlelength=1.6,
        handletextpad=0.6,
        columnspacing=2.6,
    )
    for axis in axes:
        axis.tick_params(colors=MUTED, labelsize=8.0)
    model = small_summary.get("model", "local model")
    figure.suptitle(
        f"Paired evaluation on {model}: task-scoped telemetry versus none",
        fontsize=10.4,
        color=INK,
        weight="bold",
        x=0.010,
        ha="left",
        y=0.985,
    )
    figure.text(
        0.010,
        0.012,
        "Both conditions share the prompt, tool surface, model and repository copy; only the case-scoped telemetry rows differ. Repair is decided by a held-out test the agent never sees.",
        fontsize=7.6,
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

    labels = []
    for axis in axes:
        for artist in list(axis.texts) + list(axis.get_yticklabels()) + list(axis.get_xticklabels()):
            labels.append((artist.get_text(), artist.get_window_extent(renderer=renderer)))
    for artist in figure.texts:
        labels.append((artist.get_text(), artist.get_window_extent(renderer=renderer)))
    for legend in figure.legends:
        for artist in legend.get_texts():
            labels.append((artist.get_text(), artist.get_window_extent(renderer=renderer)))

    for first in range(len(labels)):
        for second in range(first + 1, len(labels)):
            first_text, first_extent = labels[first]
            second_text, second_extent = labels[second]
            overlap_x = min(first_extent.x1, second_extent.x1) - max(first_extent.x0, second_extent.x0)
            overlap_y = min(first_extent.y1, second_extent.y1) - max(first_extent.y0, second_extent.y0)
            if overlap_x > 0.5 and overlap_y > 0.5:
                problems.append(
                    f"overlapping labels: {first_text!r} and {second_text!r} "
                    f"(overlap {overlap_x:.1f}x{overlap_y:.1f} px)"
                )
    return problems


def main():
    parser = argparse.ArgumentParser(description="Render the paired evaluation figure")
    parser.add_argument("--summary", default=str(SUMMARY))
    parser.add_argument("--runs", default=str(RUNS))
    parser.add_argument("--summary-large", default=str(SUMMARY_LARGE))
    parser.add_argument("--runs-large", default=str(RUNS_LARGE))
    parser.add_argument("--output", default=str(OUTPUT))
    args = parser.parse_args()

    small = load(Path(args.summary), Path(args.runs))
    if small[0] is None:
        raise SystemExit(f"Missing {args.summary}; run eval/eval_runner.py first.")
    large = load(Path(args.summary_large), Path(args.runs_large))

    figure, axes = build(small, large)
    problems = validate(figure, axes)
    figure.savefig(args.output, dpi=DPI, facecolor="white", bbox_inches="tight", pad_inches=0.12)
    plt.close(figure)
    print(f"Created {args.output}")
    for problem in problems:
        print(f"LAYOUT WARNING: {problem}")
    if problems:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
