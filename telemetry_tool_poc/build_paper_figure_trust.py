from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch


ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / "figure_trust_boundaries.png"

INK = "#0f172a"
MUTED = "#475569"
SURFACE = "#f8fafc"
EDGE = "#94a3b8"
BARRIER = "#b91c1c"
SERVER = "#1e3a8a"
CLIENT = "#047857"

WIDTH, HEIGHT = 11.0, 6.2
DPI = 220

BOX_TEXTS = []
BOX_RECTS = []
FREE_TEXTS = []


def box(ax, x0, y0, x1, y1, title, body, face=SURFACE, edge=EDGE, title_color=INK, radius=1.6):
    ax.add_patch(
        FancyBboxPatch(
            (x0, y0),
            x1 - x0,
            y1 - y0,
            boxstyle=f"round,pad=0,rounding_size={radius}",
            linewidth=1.4,
            facecolor=face,
            edgecolor=edge,
            zorder=2,
        )
    )
    BOX_RECTS.append((x0, y0, x1, y1))
    title_artist = ax.text(
        (x0 + x1) / 2,
        y1 - 2.6,
        title,
        ha="center",
        va="top",
        fontsize=9.8,
        color=title_color,
        weight="bold",
        zorder=3,
    )
    BOX_TEXTS.append((title_artist, (x0, y0, x1, y1)))
    for index, line in enumerate(body):
        artist = ax.text(
            (x0 + x1) / 2,
            y1 - 6.4 - index * 3.1,
            line,
            ha="center",
            va="top",
            fontsize=8.4,
            color=MUTED,
            zorder=3,
        )
        BOX_TEXTS.append((artist, (x0, y0, x1, y1)))


def arrow(ax, start, end, color=MUTED, label=None, label_offset=(0.0, 0.0), connection=None):
    patch = FancyArrowPatch(
        start,
        end,
        arrowstyle="-|>",
        mutation_scale=11,
        linewidth=1.3,
        color=color,
        connectionstyle=connection or "arc3,rad=0",
        zorder=1,
        shrinkA=0,
        shrinkB=0,
    )
    ax.add_patch(patch)
    if label:
        artist = ax.text(
            (start[0] + end[0]) / 2 + label_offset[0],
            (start[1] + end[1]) / 2 + label_offset[1],
            label,
            ha="center",
            va="center",
            fontsize=7.6,
            color=color,
            zorder=4,
            bbox=dict(boxstyle="round,pad=0.16", facecolor="white", edgecolor="none", alpha=0.95),
        )
        FREE_TEXTS.append(artist)
    return patch


def build():
    BOX_TEXTS.clear()
    BOX_RECTS.clear()
    FREE_TEXTS.clear()

    figure, ax = plt.subplots(figsize=(WIDTH, HEIGHT), dpi=DPI)
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 58)
    ax.axis("off")

    ax.text(25, 56.3, "Reachable by the agent", ha="center", va="center", fontsize=10.2, weight="bold", color=INK)
    ax.text(76, 56.3, "Server-side only", ha="center", va="center", fontsize=10.2, weight="bold", color=SERVER)

    box(
        ax,
        4,
        43,
        46,
        52,
        "Model context",
        ["8 agent-facing functions only"],
    )
    box(
        ax,
        4,
        29,
        46,
        38,
        "Agent tool library (Python)",
        ["validation - redaction - 256 KB caps"],
    )
    box(
        ax,
        4,
        15,
        46,
        24,
        "Management API (Express)",
        ["tool-key auth - ownership - transitions"],
    )

    box(
        ax,
        57,
        43,
        95,
        52,
        "Supabase schema",
        ["cases - probes - events - RLS"],
        face="#eff6ff",
        edge="#93c5fd",
        title_color=SERVER,
    )
    box(
        ax,
        57,
        29,
        95,
        38,
        "security-definer RPCs",
        ["hash(key) -> user_id - ownership re-check"],
        face="#eff6ff",
        edge="#93c5fd",
        title_color=SERVER,
    )
    box(
        ax,
        57,
        15,
        95,
        24,
        "Server-side secrets",
        ["service key - OAuth - never in context"],
        face="#eff6ff",
        edge="#93c5fd",
        title_color=SERVER,
    )

    box(
        ax,
        4,
        1,
        95,
        9,
        "Client device",
        ["probe runtime emits case-linked events"],
        face="#ecfdf5",
        edge="#6ee7b7",
        title_color=CLIENT,
    )

    arrow(ax, (17, 43), (17, 38), label="tool call", label_offset=(7.0, 0.0))
    arrow(ax, (17, 29), (17, 24), label="validated request", label_offset=(9.5, 0.0))
    arrow(ax, (36, 24), (36, 29), label="bounded JSON", label_offset=(7.5, 0.0))
    arrow(ax, (36, 38), (36, 43), label="redacted result", label_offset=(7.5, 0.0))

    arrow(
        ax,
        (46, 19.5),
        (57, 33.5),
        color=SERVER,
        label="server-side call",
        label_offset=(0.0, 4.2),
        connection="arc3,rad=0.18",
    )
    arrow(ax, (64, 24), (64, 29), color=SERVER, label="uses key", label_offset=(6.5, 0.0))
    arrow(ax, (64, 38), (64, 43), color=SERVER, label="reads rows", label_offset=(6.5, 0.0))

    arrow(ax, (17, 9), (17, 15), color=CLIENT, label="events", label_offset=(5.5, 0.0))
    arrow(ax, (36, 15), (36, 9), color=CLIENT, label="probes", label_offset=(5.0, 0.0))

    ax.plot(
        [52.5, 52.5],
        [10.5, 54.5],
        color=BARRIER,
        linewidth=1.5,
        linestyle=(0, (4, 3)),
        zorder=1,
    )
    boundary = ax.text(
        50.4,
        41,
        "server-enforced boundary",
        rotation=90,
        ha="center",
        va="center",
        fontsize=8.4,
        color=BARRIER,
        weight="bold",
        bbox=dict(boxstyle="round,pad=0.2", facecolor="white", edgecolor="none", alpha=0.95),
    )
    FREE_TEXTS.append(boundary)
    ax.plot([51.2, 53.8], [12.2, 14.8], color=BARRIER, linewidth=1.8, zorder=4)
    ax.plot([53.8, 51.2], [12.2, 14.8], color=BARRIER, linewidth=1.8, zorder=4)

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
            problems.append(f"text outside box: {artist.get_text()!r} spans ({left:.1f},{bottom:.1f})-({right:.1f},{top:.1f}) box {rect}")
    for artist in FREE_TEXTS:
        extent = artist.get_window_extent(renderer=renderer)
        left, bottom = ax.transData.inverted().transform((extent.x0, extent.y0))
        right, top = ax.transData.inverted().transform((extent.x1, extent.y1))
        for rect in BOX_RECTS:
            x0, y0, x1, y1 = rect
            if left < x1 and right > x0 and bottom < y1 and top > y0:
                problems.append(f"label overlaps box: {artist.get_text()!r} vs {rect}")
    for index, first in enumerate(BOX_RECTS):
        for second in BOX_RECTS[index + 1 :]:
            x0, y0, x1, y1 = first
            a0, b0, a1, b1 = second
            if x0 < a1 and x1 > a0 and y0 < b1 and y1 > b0:
                problems.append(f"boxes overlap: {first} vs {second}")
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
