import re
from pathlib import Path
from xml.sax import saxutils

from reportlab.lib import colors
from reportlab.lib.enums import TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase.pdfdoc import PDFDestinationFitH, PDFName
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    Image,
    KeepTogether,
    PageTemplate,
    Paragraph,
    Preformatted,
    Spacer,
    Table,
    TableStyle,
)


ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "PAPER_DRAFT.md"
FIGURE = ROOT / "figure_closed_loop.png"
OUTPUT = ROOT / "Remote_Telemetry_Tool_Paper.pdf"

PAGE_WIDTH, PAGE_HEIGHT = A4
LEFT_MARGIN = 22 * mm
RIGHT_MARGIN = 22 * mm
TOP_MARGIN = 20 * mm
BOTTOM_MARGIN = 18 * mm
CONTENT_WIDTH = PAGE_WIDTH - LEFT_MARGIN - RIGHT_MARGIN

RUNNING_TITLE = "Remote Client Telemetry for Repository-Level Coding Agents"

TABLE_CAPTIONS = [
    "Agent-facing tool surface and the bounds enforced before each call.",
    "Case state machine enforced in the Express layer and in the Supabase RPCs.",
    "Local test suites and their results.",
]

FIGURE_CAPTIONS = {
    "figure_trust_boundaries.png": (
        "Figure 1. Trust boundaries: the agent reaches only the tool surface, while ownership checks, "
        "redaction, and the database stay server-side."
    ),
    "figure_closed_loop.png": (
        "Figure 2. The closed debugging loop: evidence collection is separated from repair validation, "
        "and instrumentation is withdrawn at cleanup."
    ),
    "figure_state_machine.png": (
        "Figure 3. The server-enforced case state machine. Transitions are validated twice, in the Express "
        "layer and in the RPCs, and only the user can approve a fix."
    ),
}

INK = colors.HexColor("#0f172a")
MUTED = colors.HexColor("#334155")
RULE = colors.HexColor("#cbd5e1")
ACCENT = colors.HexColor("#1d4ed8")
CODE_BG = colors.HexColor("#f8fafc")
TABLE_HEAD_BG = colors.HexColor("#eef2ff")
TABLE_LINE = colors.HexColor("#c7d2fe")


def build_styles():
    base = getSampleStyleSheet()
    styles = {
        "title": ParagraphStyle(
            "PaperTitle",
            parent=base["Title"],
            fontName="Helvetica-Bold",
            fontSize=17,
            leading=21,
            alignment=0,
            spaceAfter=8,
            textColor=INK,
        ),
        "h2": ParagraphStyle(
            "Section",
            parent=base["Heading1"],
            fontName="Helvetica-Bold",
            fontSize=12.5,
            leading=15,
            spaceBefore=11,
            spaceAfter=5,
            textColor=INK,
        ),
        "h3": ParagraphStyle(
            "Subsection",
            parent=base["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=10.5,
            leading=13,
            spaceBefore=8,
            spaceAfter=4,
            textColor=ACCENT,
        ),
        "body": ParagraphStyle(
            "Body",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=9.4,
            leading=13.2,
            alignment=TA_JUSTIFY,
            spaceAfter=6,
            textColor=INK,
        ),
        "bullet": ParagraphStyle(
            "Bullet",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=9.4,
            leading=13.2,
            alignment=TA_JUSTIFY,
            leftIndent=12,
            bulletIndent=3,
            spaceAfter=3,
            textColor=INK,
        ),
        "quote": ParagraphStyle(
            "Quote",
            parent=base["BodyText"],
            fontName="Helvetica-Oblique",
            fontSize=9.6,
            leading=13.4,
            leftIndent=10,
            borderPadding=(4, 4, 4, 8),
            borderWidth=0.6,
            borderColor=RULE,
            backColor=colors.HexColor("#f8fafc"),
            spaceBefore=4,
            spaceAfter=8,
            textColor=INK,
        ),
        "code": ParagraphStyle(
            "Code",
            parent=base["Code"],
            fontName="Courier",
            fontSize=8.1,
            leading=10.6,
            leftIndent=6,
            spaceAfter=0,
            textColor=INK,
        ),
        "caption": ParagraphStyle(
            "Caption",
            parent=base["BodyText"],
            fontName="Helvetica-Oblique",
            fontSize=8.8,
            leading=11.6,
            spaceBefore=3,
            spaceAfter=10,
            textColor=MUTED,
        ),
        "cell": ParagraphStyle(
            "Cell",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=7.9,
            leading=10.2,
            textColor=INK,
        ),
        "cell_head": ParagraphStyle(
            "CellHead",
            parent=base["BodyText"],
            fontName="Helvetica-Bold",
            fontSize=7.9,
            leading=10.2,
            textColor=INK,
        ),
    }
    return styles


def escape(text):
    return saxutils.escape(text)


def plain_text(text):
    return re.sub(r"[`*]", "", text).strip()


class BookmarkParagraph(Paragraph):
    def drawOn(self, canvas, x, y, _sW=0):
        self.bookmark_top = y + self.height
        super().drawOn(canvas, x, y, _sW)


def heading(text, style, level):
    paragraph = BookmarkParagraph(inline(text), style)
    paragraph._bookmark_title = plain_text(text)
    paragraph._bookmark_level = level
    paragraph.bookmark_top = None
    return paragraph


def inline(text):
    parts = []
    pattern = re.compile(r"(`[^`]+`|\*\*[^*]+\*\*|\*[^*]+\*)")
    for token in pattern.split(text):
        if not token:
            continue
        if token.startswith("`") and token.endswith("`"):
            parts.append(f'<font face="Courier" size="8.1">{escape(token[1:-1])}</font>')
        elif token.startswith("**") and token.endswith("**"):
            parts.append(f"<b>{escape(token[2:-2])}</b>")
        elif token.startswith("*") and token.endswith("*"):
            parts.append(f"<i>{escape(token[1:-1])}</i>")
        else:
            parts.append(escape(token))
    return "".join(parts)


def paragraph_style_for(text):
    if "http" in text:
        style = ParagraphStyle(
            "LinkSafe",
            parent=build_styles()["body"],
            wordWrap="CJK",
        )
        return style
    return None


def parse_blocks(markdown):
    blocks = []
    lines = markdown.splitlines()
    index = 0
    while index < len(lines):
        line = lines[index]
        stripped = line.strip()
        if not stripped:
            index += 1
            continue
        if stripped.startswith("```"):
            index += 1
            code = []
            while index < len(lines) and not lines[index].strip().startswith("```"):
                code.append(lines[index])
                index += 1
            index += 1
            blocks.append(("code", "\n".join(code)))
            continue
        if stripped.startswith("|"):
            rows = []
            while index < len(lines) and lines[index].strip().startswith("|"):
                rows.append([cell.strip() for cell in lines[index].strip().strip("|").split("|")])
                index += 1
            if len(rows) > 1 and all(re.fullmatch(r":?-{2,}:?", cell) for cell in rows[1]):
                rows.pop(1)
            blocks.append(("table", rows))
            continue
        image_match = re.fullmatch(r"!\[([^\]]*)\]\(([^)]+)\)", stripped)
        if image_match:
            blocks.append(("image", (image_match.group(1), image_match.group(2))))
            index += 1
            continue
        heading_match = re.match(r"^(#{1,6})\s+(.*)$", stripped)
        if heading_match:
            blocks.append((f"h{len(heading_match.group(1))}", heading_match.group(2).strip()))
            index += 1
            continue
        if stripped.startswith(">"):
            quote = []
            while index < len(lines) and lines[index].strip().startswith(">"):
                quote.append(lines[index].strip().lstrip(">").strip())
                index += 1
            blocks.append(("quote", " ".join(quote)))
            continue
        numbered = re.match(r"^(\d+)\.\s+(.*)$", stripped)
        if numbered:
            blocks.append(("number", (numbered.group(1), numbered.group(2))))
            index += 1
            continue
        if stripped.startswith("- "):
            blocks.append(("bullet", stripped[2:].strip()))
            index += 1
            continue
        paragraph = []
        while index < len(lines) and lines[index].strip() and not lines[index].strip().startswith(("#", "|", "```", "> ", "- ")) and not re.match(r"^\d+\.\s", lines[index].strip()):
            paragraph.append(lines[index].strip())
            index += 1
        blocks.append(("paragraph", " ".join(paragraph)))
    return blocks


def build_table(rows, styles):
    header = [Paragraph(inline(cell), styles["cell_head"]) for cell in rows[0]]
    body = [[Paragraph(inline(cell), styles["cell"]) for cell in row] for row in rows[1:]]
    data = [header] + body
    weights = []
    for column in range(len(rows[0])):
        longest = max(len(re.sub(r"[`*]", "", row[column])) for row in rows)
        weights.append(min(max(longest, 8), 46))
    total = sum(weights)
    widths = [CONTENT_WIDTH * weight / total for weight in weights]
    table = Table(data, colWidths=widths, repeatRows=1, hAlign="LEFT")
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), TABLE_HEAD_BG),
                ("TEXTCOLOR", (0, 0), (-1, 0), INK),
                ("LINEBELOW", (0, 0), (-1, 0), 0.7, TABLE_LINE),
                ("LINEBELOW", (0, 1), (-1, -2), 0.3, RULE),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]
        )
    )
    return table


def build_code_block(code, styles):
    preformatted = Preformatted(code, styles["code"])
    wrapper = Table([[preformatted]], colWidths=[CONTENT_WIDTH], hAlign="LEFT")
    wrapper.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), CODE_BG),
                ("BOX", (0, 0), (-1, -1), 0.5, RULE),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]
        )
    )
    return wrapper


def build_figure(alt, path, styles):
    figure_path = (SOURCE.parent / path).resolve()
    if not figure_path.exists():
        return [Paragraph(inline(alt), styles["body"])]
    reader = ImageReader(str(figure_path))
    image_width, image_height = reader.getSize()
    width = CONTENT_WIDTH
    height = width * image_height / image_width
    image = Image(str(figure_path), width=width, height=height)
    image.hAlign = "CENTER"
    caption = FIGURE_CAPTIONS.get(Path(path).name, inline(alt))
    return [image, Paragraph(caption, styles["caption"])]


def render(markdown, styles):
    story = []
    table_index = 0
    for kind, payload in parse_blocks(markdown):
        if kind == "h1":
            story.append(heading(payload, styles["title"], 0))
        elif kind == "h2":
            story.append(heading(payload, styles["h2"], 1))
        elif kind == "h3":
            story.append(heading(payload, styles["h3"], 2))
        elif kind == "paragraph":
            style = paragraph_style_for(payload) or styles["body"]
            story.append(Paragraph(inline(payload), style))
        elif kind == "quote":
            story.append(Paragraph(inline(payload), styles["quote"]))
        elif kind == "bullet":
            story.append(Paragraph(inline(payload), styles["bullet"], bulletText="\u2022"))
        elif kind == "number":
            number, text = payload
            story.append(Paragraph(inline(text), styles["bullet"], bulletText=f"{number}."))
        elif kind == "code":
            story.append(Spacer(1, 3))
            story.append(build_code_block(payload, styles))
            story.append(Spacer(1, 8))
        elif kind == "table":
            story.append(build_table(payload, styles))
            if table_index < len(TABLE_CAPTIONS):
                story.append(Paragraph(f"Table {table_index + 1}. {TABLE_CAPTIONS[table_index]}", styles["caption"]))
            table_index += 1
        elif kind == "image":
            alt, path = payload
            story.extend(build_figure(alt, path, styles))
    return story


def decorate(canvas, document):
    canvas.saveState()
    canvas.setFont("Helvetica-Oblique", 8.2)
    canvas.setFillColor(MUTED)
    canvas.drawString(LEFT_MARGIN, PAGE_HEIGHT - TOP_MARGIN + 8 * mm, RUNNING_TITLE)
    canvas.setStrokeColor(RULE)
    canvas.setLineWidth(0.5)
    canvas.line(LEFT_MARGIN, PAGE_HEIGHT - TOP_MARGIN + 5 * mm, PAGE_WIDTH - RIGHT_MARGIN, PAGE_HEIGHT - TOP_MARGIN + 5 * mm)
    canvas.setFont("Helvetica", 8.4)
    canvas.setFillColor(MUTED)
    canvas.drawCentredString(PAGE_WIDTH / 2, BOTTOM_MARGIN - 8 * mm, f"Page {document.page}")
    canvas.restoreState()


class PaperDocTemplate(BaseDocTemplate):
    def afterFlowable(self, flowable):
        title = getattr(flowable, "_bookmark_title", None)
        if not title:
            return
        level = getattr(flowable, "_bookmark_level", 0)
        self._bookmark_counter = getattr(self, "_bookmark_counter", 0) + 1
        key = f"section-{self._bookmark_counter}"
        top = getattr(flowable, "bookmark_top", None)
        self.canv.bookmarkPage(key, fit="XYZ", left=None, top=top, zoom=None)
        self.canv.addOutlineEntry(title, key, level=level, closed=False)

    def _endBuild(self):
        pdf_doc = self.canv._doc
        first_page = pdf_doc.Pages.pages[0]
        pdf_doc.Catalog.OpenAction = PDFDestinationFitH(first_page, PAGE_HEIGHT)
        pdf_doc.Catalog.setPageMode("UseOutlines")
        pdf_doc.Catalog.setPageLayout("OneColumn")
        super()._endBuild()


def main():
    styles = build_styles()
    markdown = SOURCE.read_text(encoding="utf-8")
    story = render(markdown, styles)
    document = PaperDocTemplate(
        str(OUTPUT),
        pagesize=A4,
        leftMargin=LEFT_MARGIN,
        rightMargin=RIGHT_MARGIN,
        topMargin=TOP_MARGIN,
        bottomMargin=BOTTOM_MARGIN,
        title="Remote Client Telemetry for Repository-Level Coding Agents: A Closed-Loop Debugging Protocol",
        author="PaperTrack prototype team",
        subject="Kaggle - The Gemma 4 Developer Agent Paper Track",
    )
    frame = Frame(
        LEFT_MARGIN,
        BOTTOM_MARGIN,
        CONTENT_WIDTH,
        PAGE_HEIGHT - TOP_MARGIN - BOTTOM_MARGIN,
        id="body",
        leftPadding=0,
        rightPadding=0,
        topPadding=0,
        bottomPadding=0,
    )
    document.addPageTemplates([PageTemplate(id="paper", frames=[frame], onPage=decorate)])
    document.build(story)
    print(f"Created {OUTPUT}")


if __name__ == "__main__":
    main()
