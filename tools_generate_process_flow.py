"""
Generates a process-flow diagram PDF from the APPLE-ORANGE master BPCR.
Boxes = operations, diamond = the IPC-1 decision point, side branch =
the conditional Orange addition (Table-2 recheck loop).
"""

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm
from reportlab.lib.colors import HexColor

PAGE_W, PAGE_H = A4
BOX_W = 130 * mm
BOX_H = 16 * mm
LEFT_X = (PAGE_W - BOX_W) / 2
TOP_Y = PAGE_H - 30 * mm
GAP = 22 * mm

BOX_FILL = HexColor("#eaf2ff")
BOX_BORDER = HexColor("#2c5aa0")
DECISION_FILL = HexColor("#fff3cd")
DECISION_BORDER = HexColor("#b8860b")
BRANCH_FILL = HexColor("#f8d7da")
BRANCH_BORDER = HexColor("#a94442")
TEXT_COLOR = HexColor("#1a1a1a")

STEPS = [
    ("OP-01", "Check reactor SSR-101/SSR-102 is clean"),
    ("OP-02", "Charge IPA 500 L into reactor"),
    ("OP-03", "Charge APPLE 100 kg + Orange 70 kg into reactor"),
    ("OP-04", "Heat to reflux (85-90 degC), maintain RPM 5-15"),
    ("OP-05", "Hold 87+-2 degC x 3 hrs, log Table-1 every 30+-5 min"),
]

DECISION = ("IPC-1", "APPLE result NMT 1.5% area?")

BRANCH_STEP = ("OP-06", "If FAIL: add Orange 10 kg, hold 2 more hrs,\nlog Table-2 every 15+-5 min, recheck IPC-2")

STEPS_AFTER = [
    ("OP-07", "Distil mass to HT (300-350 L), transfer to GLR"),
    ("OP-08", "Charge 1000 L water, distil to 800 L in HT"),
    ("OP-09", "Filter off water, dry >= 8 hrs"),
    ("OP-10", "Unload to containers, send sample to QC"),
]


def draw_box(c, x, y, w, h, text_lines, fill, border, font_size=9):
    c.setFillColor(fill)
    c.setStrokeColor(border)
    c.setLineWidth(1.2)
    c.roundRect(x, y, w, h, 4 * mm, fill=1, stroke=1)
    c.setFillColor(TEXT_COLOR)
    c.setFont("Helvetica", font_size)
    line_height = font_size + 2
    total_h = line_height * len(text_lines)
    start_y = y + h / 2 + total_h / 2 - line_height
    for i, line in enumerate(text_lines):
        c.drawCentredString(x + w / 2, start_y - i * line_height, line)


def draw_diamond(c, cx, cy, w, h, text_lines, fill, border, font_size=9):
    c.setFillColor(fill)
    c.setStrokeColor(border)
    c.setLineWidth(1.2)
    p = c.beginPath()
    p.moveTo(cx, cy + h / 2)
    p.lineTo(cx + w / 2, cy)
    p.lineTo(cx, cy - h / 2)
    p.lineTo(cx - w / 2, cy)
    p.close()
    c.drawPath(p, fill=1, stroke=1)
    c.setFillColor(TEXT_COLOR)
    c.setFont("Helvetica-Bold", font_size)
    line_height = font_size + 2
    total_h = line_height * len(text_lines)
    start_y = cy + total_h / 2 - line_height
    for i, line in enumerate(text_lines):
        c.drawCentredString(cx, start_y - i * line_height, line)


def draw_arrow(c, x, y_top, y_bottom, color=HexColor("#555555")):
    c.setStrokeColor(color)
    c.setLineWidth(1.2)
    c.line(x, y_top, x, y_bottom)
    c.line(x, y_bottom, x - 2 * mm, y_bottom + 3 * mm)
    c.line(x, y_bottom, x + 2 * mm, y_bottom + 3 * mm)


def wrap_op_text(op_id, desc, width_chars=32):
    import textwrap
    wrapped = textwrap.wrap(desc, width_chars)
    return [f"{op_id}"] + wrapped


def build_flow_pdf(output_path: str):
    c = canvas.Canvas(output_path, pagesize=A4)

    c.setFont("Helvetica-Bold", 16)
    c.setFillColor(TEXT_COLOR)
    c.drawCentredString(PAGE_W / 2, PAGE_H - 15 * mm, "APPLE-ORANGE Batch Process — Flow Diagram")
    c.setFont("Helvetica", 9)
    c.setFillColor(HexColor("#555555"))
    c.drawCentredString(PAGE_W / 2, PAGE_H - 21 * mm, "Derived from Master BPCR — for visual QA reference and spec verification")

    y = TOP_Y
    center_x = PAGE_W / 2

    # Steps 1-5
    for op_id, desc in STEPS:
        draw_box(c, LEFT_X, y - BOX_H, BOX_W, BOX_H, wrap_op_text(op_id, desc), BOX_FILL, BOX_BORDER)
        draw_arrow(c, center_x, y - BOX_H, y - BOX_H - GAP + BOX_H)
        y -= GAP

    # Decision diamond
    diamond_h = 26 * mm
    diamond_cy = y - diamond_h / 2
    draw_diamond(c, center_x, diamond_cy, 90 * mm, diamond_h,
                 [DECISION[0], DECISION[1]], DECISION_FILL, DECISION_BORDER)

    # Branch arrow to the right -> OP-06
    branch_y = diamond_cy
    c.setStrokeColor(BRANCH_BORDER)
    c.setLineWidth(1.2)
    c.line(center_x + 45 * mm, branch_y, center_x + 65 * mm, branch_y)
    c.setFont("Helvetica-Oblique", 8)
    c.setFillColor(BRANCH_BORDER)
    c.drawString(center_x + 47 * mm, branch_y + 2 * mm, "FAIL (>=1.5%)")

    branch_box_w = 55 * mm
    branch_box_h = 22 * mm
    branch_x = center_x + 65 * mm
    branch_y_top = branch_y + branch_box_h / 2
    draw_box(c, branch_x, branch_y_top - branch_box_h, branch_box_w, branch_box_h,
             wrap_op_text(BRANCH_STEP[0], BRANCH_STEP[1], width_chars=22),
             BRANCH_FILL, BRANCH_BORDER, font_size=7.5)
    # loop-back arrow from branch box down to next main step's height
    c.setStrokeColor(BRANCH_BORDER)
    c.line(branch_x + branch_box_w / 2, branch_y_top - branch_box_h,
           branch_x + branch_box_w / 2, diamond_cy - diamond_h / 2 - GAP + BOX_H / 2)
    c.line(branch_x + branch_box_w / 2, diamond_cy - diamond_h / 2 - GAP + BOX_H / 2,
           center_x + 45 * mm, diamond_cy - diamond_h / 2 - GAP + BOX_H / 2)

    # PASS arrow straight down
    c.setStrokeColor(HexColor("#28a745"))
    c.setFont("Helvetica-Oblique", 8)
    c.setFillColor(HexColor("#28a745"))
    c.drawString(center_x + 3 * mm, diamond_cy - diamond_h / 2 - 5 * mm, "PASS (<1.5%)")
    draw_arrow(c, center_x, diamond_cy - diamond_h / 2, diamond_cy - diamond_h / 2 - GAP + BOX_H, HexColor("#28a745"))

    y = diamond_cy - diamond_h / 2 - GAP

    # Steps 7-10
    for op_id, desc in STEPS_AFTER:
        draw_box(c, LEFT_X, y - BOX_H, BOX_W, BOX_H, wrap_op_text(op_id, desc), BOX_FILL, BOX_BORDER)
        if (op_id, desc) != STEPS_AFTER[-1]:
            draw_arrow(c, center_x, y - BOX_H, y - BOX_H - GAP + BOX_H)
        y -= GAP

    # Legend
    legend_y = 20 * mm
    c.setFont("Helvetica", 8)
    c.setFillColor(TEXT_COLOR)
    c.setFillColor(BOX_FILL)
    c.rect(LEFT_X, legend_y, 6 * mm, 4 * mm, fill=1, stroke=0)
    c.setFillColor(TEXT_COLOR)
    c.drawString(LEFT_X + 8 * mm, legend_y + 1 * mm, "Standard operation")
    c.setFillColor(DECISION_FILL)
    c.rect(LEFT_X + 55 * mm, legend_y, 6 * mm, 4 * mm, fill=1, stroke=0)
    c.setFillColor(TEXT_COLOR)
    c.drawString(LEFT_X + 63 * mm, legend_y + 1 * mm, "IPC decision point")
    c.setFillColor(BRANCH_FILL)
    c.rect(LEFT_X + 100 * mm, legend_y, 6 * mm, 4 * mm, fill=1, stroke=0)
    c.setFillColor(TEXT_COLOR)
    c.drawString(LEFT_X + 108 * mm, legend_y + 1 * mm, "Conditional branch")

    c.showPage()
    c.save()


if __name__ == "__main__":
    build_flow_pdf("/mnt/user-data/outputs/apple_orange_process_flow.pdf")
    print("done")
