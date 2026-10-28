from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch


ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / "figure_state_machine.png"

INK = "#1e1b4b"
MUTED = "#475569"
EDGE = "#6366f1"
FILL = "#eef2ff"
TERMINAL_FILL = "#f1f5f9"
TERMINAL_EDGE = "#334155"
ARROW = "#64748b"
RETURN = "#94a3b8"

WIDTH, HEIGHT = 11.0, 4.9
DPI = 220

BOX_TEXTS = []
BOX_RECTS = []
FREE_TEXTS = []


def state(ax, x0, y0, x1, y1, name, meaning, terminal=False):
    face = TERMINAL_FILL if terminal else FILL
    edge = TERMINAL_EDGE if terminal else EDGE
    ax.add_patch(
        FancyBboxPatch(
            (x0, y0),
            x1 - x0,
            y1 - y0,
            boxstyle="round,pad=0,rounding_size=1.4",
            linewidth=1.4,
            facecolor=face,
            edgecolor=edge,
            zorder=2,
        )
    )
    if terminal:
        ax.add_patch(
            FancyBboxPatch(
                (x0 - 0.9, y0 - 0.9),
                x1 - x0 + 1.8,
                y1 - y0 + 1.8,
                boxstyle="round,pad=0,rounding_size=2.0",
                linewidth=0.9,
                facecolor="none",
                edgecolor=TERMINAL_EDGE,
                zorder=1,
            )
        )
    BOX_RECTS.append((x0, y0, x1, y1))
    title = ax.text(
        (x0 + x1) / 2,
        y1 - 1.9,
        name,
        ha="center",
        va="top",
        fontsize=9.4,
        weight="bold",
        color=TERMINAL_EDGE if terminal else INK,
        zorder=3,
    )
    BOX_TEXTS.append((title, (x0, y0, x1, y1)))
    body = ax.text(
        (x0 + x1) / 2,
        y1 - 5.0,
        meaning,
        ha="center",
        va="top",
        fontsize=7.8,
        color=MUTED,
        zorder=3,
    )
    BOX_TEXTS.append((body, (x0, y0, x1, y1)))


def arrow(ax, start, end, label=None, label_xy=None, color=ARROW, dashed=False, ha="center", rotation=0.0):
    patch = FancyArrowPatch(
        start,
        end,
        arrowstyle="-|>",
        mutation_scale=10,
        linewidth=1.25,
        color=color,
        linestyle=(0, (4, 2.5)) if dashed else "solid",
        connectionstyle="arc3,rad=0",
        zorder=1,
        shrinkA=0,
        shrinkB=0,
    )
    ax.add_patch(patch)
    if label:
        artist = ax.text(
            label_xy[0],
            label_xy[1],
            label,
            ha=ha,
            va="center",
            fontsize=7.6,
            color=MUTED,
            rotation=rotation,
            zorder=4,
            bbox=dict(boxstyle="round,pad=0.15", facecolor="white", edgecolor="none", alpha=0.95),
        )
        FREE_TEXTS.append(artist)
    return patch


def build():
    BOX_TEXTS.clear()
    BOX_RECTS.clear()
    FREE_TEXTS.clear()

    figure, ax = plt.subplots(figsize=(WIDTH, HEIGHT), dpi=DPI)
    ax.set_xlim(0, 122)
    ax.set_ylim(-2, 46)
    ax.axis("off")

    state(ax, 2, 32, 18, 44, "reported", "failure reported")
    state(ax, 22, 32, 44, 44, "instrumenting", "probes live")
    state(ax, 48, 32, 74, 44, "awaiting_recheck", "reproduction asked")
    state(ax, 78, 32, 96, 44, "rechecked", "outcome in")
    state(ax, 100, 32, 122, 44, "patch_ready", "fix ready")

    state(ax, 2, 17, 24, 29, "abandoned", "ended", terminal=True)
    state(ax, 62, 17, 84, 29, "rejected", "fix refused")
    state(ax, 100, 17, 122, 29, "approved", "fix accepted")
    state(ax, 100, 2, 122, 14, "resolved", "cleaned up", terminal=True)

    arrow(ax, (18, 38), (22, 38))
    arrow(ax, (44, 38), (48, 38))
    arrow(ax, (74, 38), (78, 38))
    arrow(ax, (96, 38), (100, 38), label="finalize", label_xy=(98, 45.2))

    arrow(ax, (111, 32), (111, 29), label="user approves", label_xy=(108.5, 30.4), ha="right")
    arrow(ax, (111, 17), (111, 14), label="cleanup deletes logs, probes off", label_xy=(107.5, 15.4), ha="right")
    arrow(ax, (100, 32), (84, 29), label="user rejects", label_xy=(93.5, 30.4))

    arrow(ax, (62, 23), (42, 32), label="re-instrument", label_xy=(51, 26.0), color=RETURN, dashed=True, rotation=-22)
    arrow(ax, (26, 32), (14, 29), label="abandon", label_xy=(19.5, 31.2), color=RETURN, dashed=True)

    note = ax.text(
        13,
        12.5,
        "allowed from any\nnon-terminal state",
        ha="center",
        va="center",
        fontsize=7.4,
        color=MUTED,
        zorder=3,
    )
    FREE_TEXTS.append(note)

    legend = ax.text(
        30,
        5,
        "double border = terminal state",
        ha="left",
        va="center",
        fontsize=7.6,
        color=MUTED,
        zorder=3,
    )
    FREE_TEXTS.append(legend)

    return figure, ax


def validate(figure, ax):
    figure.canvas.draw()
    renderer = figure.canvas.get_renderer()
    problems = []
    for artist, rect in BOX_TEXTS:
        extent = artist.get_window_extent(renderer=renderer)
        left, bottom = ax.transData.inverted().transform((extent.x0, extent.y0))
        right, top = ax.transData.inverted().transform((extent.x1, extent.y1))
        x0, y0, x1, y1 = rect
        if left < x0 - 0.4 or right > x1 + 0.4 or bottom < y0 - 0.4 or top > y1 + 0.4:
            problems.append(f"text outside state: {artist.get_text()!r} spans ({left:.1f},{bottom:.1f})-({right:.1f},{top:.1f}) box {rect}")
    for artist in FREE_TEXTS:
        extent = artist.get_window_extent(renderer=renderer)
        left, bottom = ax.transData.inverted().transform((extent.x0, extent.y0))
        right, top = ax.transData.inverted().transform((extent.x1, extent.y1))
        for rect in BOX_RECTS:
            x0, y0, x1, y1 = rect
            if left < x1 and right > x0 and bottom < y1 and top > y0:
                problems.append(f"label overlaps state: {artist.get_text()!r} vs {rect}")
    for index, first in enumerate(BOX_RECTS):
        for second in BOX_RECTS[index + 1 :]:
            x0, y0, x1, y1 = first
            a0, b0, a1, b1 = second
            if x0 < a1 and x1 > a0 and y0 < b1 and y1 > b0:
                problems.append(f"states overlap: {first} vs {second}")
    return problems


def main():
    figure, ax = build()
    problems = validate(figure, ax)
    figure.savefig(OUTPUT, dpi=DPI, facecolor="white", bbox_inches="tight", pad_inches=0.12)
    plt.close(figure)
    print(f"Created {OUTPUT}")
    for problem in problems:
        print(f"LAYOUT WARNING: {problem}")
    if problems:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
