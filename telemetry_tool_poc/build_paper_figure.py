from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / "figure_closed_loop.png"

CANVAS = (1800, 1000)
FONT_DIR = Path("C:/Windows/Fonts")

COLORS = {
    "user": ((251, 191, 36), (120, 80, 5)),
    "agent": ((96, 165, 250), (23, 58, 115)),
    "client": ((52, 211, 153), (6, 78, 59)),
    "close": ((203, 213, 225), (51, 65, 85)),
    "ink": (15, 23, 42),
    "muted": (51, 65, 85),
    "line": (51, 65, 85),
    "paper": (255, 255, 255),
}


def font(size, bold=False):
    name = "arialbd.ttf" if bold else "arial.ttf"
    return ImageFont.truetype(str(FONT_DIR / name), size)


def centered(draw, box, title, subtitle, title_font, subtitle_font, title_color, subtitle_color):
    left, top, right, bottom = box
    title_box = draw.textbbox((0, 0), title, font=title_font)
    title_height = title_box[3] - title_box[1]
    subtitle_box = draw.textbbox((0, 0), subtitle, font=subtitle_font)
    subtitle_height = subtitle_box[3] - subtitle_box[1]
    total = title_height + 10 + subtitle_height
    y = top + ((bottom - top) - total) / 2
    width = title_box[2] - title_box[0]
    draw.text((left + ((right - left) - width) / 2, y), title, font=title_font, fill=title_color)
    y += title_height + 10
    width = subtitle_box[2] - subtitle_box[0]
    draw.text((left + ((right - left) - width) / 2, y), subtitle, font=subtitle_font, fill=subtitle_color)


def rounded_box(draw, box, fill, outline, radius=18, width=3):
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def arrow(draw, start, end, color, width=4, head=16, dashed=False):
    x1, y1 = start
    x2, y2 = end
    if dashed:
        import math

        length = math.hypot(x2 - x1, y2 - y1)
        steps = max(int(length // 22), 1)
        for index in range(steps):
            if index % 2:
                continue
            t1 = index / steps
            t2 = min((index + 1) / steps, 1)
            draw.line(
                (x1 + (x2 - x1) * t1, y1 + (y2 - y1) * t1, x1 + (x2 - x1) * t2, y1 + (y2 - y1) * t2),
                fill=color,
                width=width,
            )
    else:
        draw.line((x1, y1, x2, y2), fill=color, width=width)
    import math

    angle = math.atan2(y2 - y1, x2 - x1)
    left = (x2 - head * math.cos(angle - 0.45), y2 - head * math.sin(angle - 0.45))
    right = (x2 - head * math.cos(angle + 0.45), y2 - head * math.sin(angle + 0.45))
    draw.polygon([(x2, y2), left, right], fill=color)


def label(draw, position, text, label_font, color):
    box = draw.textbbox((0, 0), text, font=label_font)
    width = box[2] - box[0]
    height = box[3] - box[1]
    x, y = position
    draw.rectangle((x - 6, y - 3, x + width + 6, y + height + 5), fill=COLORS["paper"])
    draw.text((x, y), text, font=label_font, fill=color)


def main():
    image = Image.new("RGB", CANVAS, COLORS["paper"])
    draw = ImageDraw.Draw(image)

    title_font = font(34, bold=True)
    box_title_font = font(31, bold=True)
    box_subtitle_font = font(23)
    label_font = font(24)
    legend_font = font(27)
    legend_title_font = font(30, bold=True)

    box_width = 390
    box_height = 168
    top = 70
    bottom = 560
    gap = 40
    columns = [60 + index * (box_width + gap) for index in range(4)]

    stages = [
        (columns[0], top, "Report", "user opens a case", "user"),
        (columns[1], top, "Instrument", "agent publishes probes", "agent"),
        (columns[2], top, "Probe runtime", "client emits case events", "client"),
        (columns[3], top, "Re-check", "user reproduces and reports", "user"),
        (columns[3], bottom, "Analyze and patch", "agent reads case logs only", "agent"),
        (columns[2], bottom, "Finalize", "state becomes patch_ready", "agent"),
        (columns[1], bottom, "Approve, then clean up", "logs deleted, probes off", "close"),
    ]

    for x, y, title, subtitle, kind in stages:
        fill, outline = COLORS[kind]
        box = (x, y, x + box_width, y + box_height)
        rounded_box(draw, box, fill, outline)
        centered(draw, box, title, subtitle, box_title_font, box_subtitle_font, COLORS["ink"], COLORS["muted"])

    line_color = COLORS["line"]
    for index in range(3):
        start_x = columns[index] + box_width
        end_x = columns[index + 1]
        arrow(draw, (start_x + 6, top + box_height / 2), (end_x - 6, top + box_height / 2), line_color)

    arrow(
        draw,
        (columns[3] + box_width / 2, top + box_height + 8),
        (columns[3] + box_width / 2, bottom - 8),
        line_color,
    )

    for index in (3, 2):
        start_x = columns[index]
        end_x = columns[index - 1] + box_width
        arrow(draw, (start_x - 6, bottom + box_height / 2), (end_x + 6, bottom + box_height / 2), line_color)

    elbow_x = columns[1] + box_width / 2
    arrow(
        draw,
        (columns[3] + 120, bottom - 6),
        (elbow_x, bottom - 6),
        COLORS["agent"][1],
        dashed=True,
    )
    arrow(draw, (elbow_x, bottom - 6), (elbow_x, top + box_height + 8), COLORS["agent"][1], dashed=True)

    label(draw, (columns[0] + 96, top - 34), "case created", label_font, COLORS["muted"])
    label(draw, (columns[1] + 60, top - 34), "probes + instructions", label_font, COLORS["muted"])
    label(draw, (columns[2] + 40, top - 34), "case-linked events", label_font, COLORS["muted"])
    label(draw, (columns[3] + 46, top - 34), "re-check report", label_font, COLORS["muted"])
    label(draw, (columns[3] + 40, bottom + box_height + 14), "patch proposal", label_font, COLORS["muted"])
    label(draw, (columns[2] + 30, bottom + box_height + 14), "patch_ready", label_font, COLORS["muted"])
    label(draw, (columns[1] + 26, bottom + box_height + 14), "user approval", label_font, COLORS["muted"])
    label(draw, (elbow_x + 18, (top + box_height + bottom) / 2 - 14), "re-instrument", label_font, COLORS["agent"][1])

    legend_box = (60, 810, 1740, 975)
    rounded_box(draw, legend_box, (248, 250, 252), (120, 139, 168), radius=16, width=2)
    draw.text((legend_box[0] + 24, legend_box[1] + 28), "Server-enforced states", font=legend_title_font, fill=COLORS["ink"])
    state_lines = [
        "reported -> instrumenting -> awaiting_recheck -> rechecked -> patch_ready -> approved -> resolved",
        "rejected or abandoned returns to instrumenting; cleanup deletes the case logs and deactivates its probes",
    ]
    for index, line in enumerate(state_lines):
        draw.text((legend_box[0] + 24, legend_box[1] + 78 + index * 38), line, font=legend_font, fill=COLORS["muted"])

    image.save(OUTPUT, optimize=True)
    print(f"Created {OUTPUT} ({image.width}x{image.height})")


if __name__ == "__main__":
    main()
