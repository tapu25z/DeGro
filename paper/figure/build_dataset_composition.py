from math import cos, radians, sin
from pathlib import Path

from reportlab.lib.colors import HexColor, white
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas


OUT = Path(__file__).with_name("dataset_composition.pdf")
W, H = 240, 168

# Match the supplied chart references: Avenir Next, dark navy text, and the
# same pastel blue/green/coral/purple family with blue and amber accents.
FONT_FILE = "/System/Library/Fonts/Avenir Next.ttc"
FONT_REGULAR = "AvenirNext"
FONT_BOLD = "AvenirNext-DemiBold"
if Path(FONT_FILE).exists():
    pdfmetrics.registerFont(TTFont(FONT_REGULAR, FONT_FILE, subfontIndex=7))
    pdfmetrics.registerFont(TTFont(FONT_BOLD, FONT_FILE, subfontIndex=2))
else:
    # Keep the chart buildable on non-macOS systems.
    FONT_REGULAR = "Helvetica"
    FONT_BOLD = "Helvetica-Bold"

DARK = HexColor("#212F3F")
MUTED = HexColor("#6C797A")
COLORS = [
    HexColor("#74B3E3"),  # Algebra word problems (DRAW-Paired)
    HexColor("#B586C9"),  # LIN
    HexColor("#73DC9A"),  # RANK
    HexColor("#EB7F77"),  # PATH
    HexColor("#3D6EAC"),  # CRT
    HexColor("#F1AE45"),  # MOM
    HexColor("#6C797A"),  # GEO
]
LABELS = ["Algebra", "LIN", "RANK", "PATH", "CRT", "MOM", "GEO"]
VALUES = [300, 60, 60, 60, 60, 60, 60]
TOTAL = sum(VALUES)


def text(c, x, y, value, size=7, bold=False, align="left", color=DARK):
    c.setFillColor(color)
    c.setFont(FONT_BOLD if bold else FONT_REGULAR, size)
    if align == "center":
        c.drawCentredString(x, y, value)
    elif align == "right":
        c.drawRightString(x, y, value)
    else:
        c.drawString(x, y, value)


def draw_donut(c, cx, cy, radius, inner_radius):
    angle = 90
    for value, color in zip(VALUES, COLORS):
        extent = -360 * value / TOTAL
        c.setFillColor(color)
        c.setStrokeColor(white)
        c.setLineWidth(1.1)
        c.wedge(cx - radius, cy - radius, cx + radius, cy + radius,
                angle, extent, fill=1, stroke=1)

        mid = angle + extent / 2
        label_radius = (radius + inner_radius) / 2
        x = cx + label_radius * cos(radians(mid))
        y = cy + label_radius * sin(radians(mid))
        text(c, x, y - 2, str(value), size=6.2, bold=True,
             align="center", color=white)
        angle += extent

    c.setFillColor(white)
    c.setStrokeColor(white)
    c.circle(cx, cy, inner_radius, fill=1, stroke=1)
    text(c, cx, cy + 7, "Total", size=7, bold=True, align="center", color=MUTED)
    text(c, cx, cy - 7, str(TOTAL), size=14, bold=True, align="center")
    text(c, cx, cy - 16, "pairs", size=5.6, align="center", color=MUTED)


def draw_legend(c, x, top):
    for i, (label, value, color) in enumerate(zip(LABELS, VALUES, COLORS)):
        y = top - i * 14
        c.setFillColor(color)
        c.roundRect(x, y - 1, 7, 7, 1.2, fill=1, stroke=0)
        text(c, x + 11, y, label, size=6.3)
        text(c, 226, y, str(value), size=6.3, bold=True, align="right")


c = canvas.Canvas(str(OUT), pagesize=(W, H))
c.setTitle("DeGro paired benchmark composition")

text(c, 12, 154, "Paired benchmark composition", size=9.5, bold=True)
text(c, 12, 143, "660 pairs across two benchmarks", size=5.8, color=MUTED)

draw_donut(c, cx=72, cy=78, radius=55, inner_radius=29)
draw_legend(c, x=137, top=119)

text(c, 137, 25, "MIRA-Math: 6 families x 60", size=5.7, color=MUTED)
text(c, 137, 13, "DRAW-Paired: 300 algebra pairs", size=5.7, color=MUTED)

c.showPage()
c.save()
print(OUT)
