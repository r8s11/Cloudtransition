#!/usr/bin/env python3
"""Render the tailored CV JSON to DOCX and print-ready HTML.

Usage: python3 render_cv.py <tailored.json> <base.json> <out_basename>
Writes <out_basename>.docx and <out_basename>.html (HTML is printed to PDF by Chrome).
"""
import html
import json
import sys
from pathlib import Path

from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor

DARK = RGBColor(0x1A, 0x1A, 0x1A)
MID = RGBColor(0x44, 0x44, 0x44)
GREY = RGBColor(0x5A, 0x5A, 0x5A)


def load(tailored_path, base_path):
    t = json.loads(Path(tailored_path).read_text())
    b = json.loads(Path(base_path).read_text())
    skills = {s["category"]: s for s in b["skills"]}
    rows = []
    for cat in t["skills_order"]:
        if cat == "Languages":
            rows.append((cat, ", ".join(b["identity"]["languages"])))
        else:
            rows.append((cat, ", ".join(skills[cat]["items"])))
    return t, b, rows


def bullet_parts(text, lead=None):
    if lead and text.startswith(lead):
        return lead, text[len(lead):]
    return None, text


# ---------- DOCX ----------

def set_cell_margins(cell, top=20, bottom=20, left=0, right=60):
    tcPr = cell._tc.get_or_add_tcPr()
    mar = OxmlElement("w:tcMar")
    for tag, val in (("top", top), ("bottom", bottom), ("start", left), ("end", right)):
        node = OxmlElement(f"w:{tag}")
        node.set(qn("w:w"), str(val))
        node.set(qn("w:type"), "dxa")
        mar.append(node)
    tcPr.append(mar)


def add_bottom_border(paragraph, size=6, color="999999"):
    pPr = paragraph._p.get_or_add_pPr()
    pBdr = OxmlElement("w:pBdr")
    bottom = OxmlElement("w:bottom")
    bottom.set(qn("w:val"), "single")
    bottom.set(qn("w:sz"), str(size))
    bottom.set(qn("w:space"), "2")
    bottom.set(qn("w:color"), color)
    pBdr.append(bottom)
    pPr.append(pBdr)


def no_table_borders(table):
    tbl = table._tbl
    tblPr = tbl.tblPr
    borders = OxmlElement("w:tblBorders")
    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        el = OxmlElement(f"w:{edge}")
        el.set(qn("w:val"), "nil")
        borders.append(el)
    tblPr.append(borders)


def add_run(p, text, size=9.3, bold=False, color=DARK, italic=False):
    r = p.add_run(text)
    r.font.name = "Arial"
    r.font.size = Pt(size)
    r.bold = bold
    r.italic = italic
    r.font.color.rgb = color
    return r


def build_docx(t, b, rows, path):
    doc = Document()
    sec = doc.sections[0]
    sec.page_width, sec.page_height = Inches(8.5), Inches(11)
    sec.top_margin = Inches(0.42)
    sec.bottom_margin = Inches(0.38)
    sec.left_margin = Inches(0.55)
    sec.right_margin = Inches(0.55)

    normal = doc.styles["Normal"]
    normal.font.name = "Arial"
    normal.font.size = Pt(9.3)
    normal.paragraph_format.space_after = Pt(0)
    normal.paragraph_format.line_spacing = 1.04
    normal.element.rPr.rFonts.set(qn("w:eastAsia"), "Arial")

    # Name / headline / contact
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(1)
    add_run(p, b["identity"]["name"], size=21, bold=True)

    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(2)
    add_run(p, t["headline"], size=10, bold=True, color=MID)

    idn = b["identity"]
    contact = (
        f"{idn['location']}  |  {idn['phone']}  |  {idn['email']}  |  "
        f"chinola.app  |  github.com/r8s11  |  linkedin.com/in/rooseveltbsegura"
    )
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(2)
    add_run(p, contact, size=8.5, color=GREY)

    def heading(text):
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(6)
        p.paragraph_format.space_after = Pt(2.5)
        p.paragraph_format.keep_with_next = True
        add_run(p, text.upper(), size=9.3, bold=True)
        add_bottom_border(p)

    heading("Professional Summary")
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(1)
    p.alignment = WD_ALIGN_PARAGRAPH.LEFT
    add_run(p, t["summary"], size=9.3)

    heading("Certifications")
    for c in b["certifications"]:
        p = doc.add_paragraph()
        p.paragraph_format.space_after = Pt(1)
        add_run(p, f"{c['name']}", size=9.3, bold=True)
        add_run(p, f" — {c['issuer']} ({c['date']})", size=9.3)

    heading("Technical Skills")
    table = doc.add_table(rows=0, cols=2)
    table.alignment = WD_TABLE_ALIGNMENT.LEFT
    table.autofit = False
    no_table_borders(table)
    for cat, items in rows:
        cells = table.add_row().cells
        cells[0].width = Inches(1.55)
        cells[1].width = Inches(5.15)
        set_cell_margins(cells[0])
        set_cell_margins(cells[1])
        p0 = cells[0].paragraphs[0]
        p0.paragraph_format.space_after = Pt(1.5)
        add_run(p0, cat, size=9, bold=True)
        p1 = cells[1].paragraphs[0]
        p1.paragraph_format.space_after = Pt(1.5)
        add_run(p1, items, size=9)

    heading("Professional Experience")
    for role in t["experience"]:
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(4)
        p.paragraph_format.space_after = Pt(0)
        p.paragraph_format.keep_with_next = True
        add_run(p, role["title"], size=10, bold=True)

        p = doc.add_paragraph()
        p.paragraph_format.space_after = Pt(1.5)
        p.paragraph_format.keep_with_next = True
        add_run(p, f"{role['employer']} — {role['location']}", size=9, color=MID)
        add_run(p, f"  |  {role['dates']}", size=9, color=MID, italic=True)

        for bullet in role["bullets"]:
            p = doc.add_paragraph(style="List Bullet")
            pf = p.paragraph_format
            pf.left_indent = Inches(0.22)
            pf.first_line_indent = Inches(-0.14)
            pf.space_after = Pt(1.5)
            pf.line_spacing = 1.05
            lead, rest = bullet_parts(bullet["text"], bullet.get("bold_lead"))
            if lead:
                add_run(p, lead, size=9.5, bold=True)
                add_run(p, rest, size=9.5)
            else:
                add_run(p, bullet["text"], size=9.5)

    heading("Military Service")
    mil = t["military_service"]
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(0)
    p.paragraph_format.keep_with_next = True
    add_run(p, mil["title"], size=10, bold=True)
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(1.5)
    add_run(p, f"{mil['organization']} — {mil['location']}", size=9, color=MID)
    add_run(p, f"  |  {mil['dates']}", size=9, color=MID, italic=True)
    for text in mil["bullets"]:
        p = doc.add_paragraph(style="List Bullet")
        pf = p.paragraph_format
        pf.left_indent = Inches(0.22)
        pf.first_line_indent = Inches(-0.14)
        pf.space_after = Pt(1.5)
        add_run(p, text, size=9.5)

    doc.save(path)


# ---------- HTML ----------

def build_html(t, b, rows, path):
    e = html.escape
    idn = b["identity"]
    css = """
@page { size: Letter; margin: 0.42in 0.55in 0.38in 0.55in; }
* { box-sizing: border-box; }
body { font-family: Arial, Helvetica, sans-serif; font-size: 9.3pt; line-height: 1.24;
       color: #1a1a1a; margin: 0; }
h1 { font-size: 21pt; margin: 0 0 2pt 0; letter-spacing: 0.2pt; }
.headline { font-size: 10pt; font-weight: bold; color: #444; margin: 0 0 3pt 0; }
.contact { font-size: 8.6pt; color: #5a5a5a; margin: 0 0 2pt 0; }
h2 { font-size: 9.4pt; text-transform: uppercase; letter-spacing: 0.7pt; margin: 8pt 0 2.5pt 0;
     padding-bottom: 1.5pt; border-bottom: 0.8pt solid #999; page-break-after: avoid; }
p { margin: 0; }
.summary { text-align: left; }
ul { margin: 1pt 0 0 0; padding-left: 13pt; }
li { margin: 0 0 1.4pt 0; }
.role { margin-top: 5.5pt; page-break-inside: avoid; }
.role-title { font-size: 10pt; font-weight: bold; margin: 0; }
.role-meta { font-size: 9pt; color: #444; margin: 0 0 2pt 0; }
.role-meta .dates { font-style: italic; }
table.skills { width: 100%; border-collapse: collapse; margin-top: 1pt; }
table.skills td { vertical-align: top; padding: 0.8pt 6pt 0.8pt 0; font-size: 9pt; }
table.skills td.cat { width: 21%; font-weight: bold; white-space: nowrap; }
.cert { margin-bottom: 1.5pt; }
a { color: inherit; text-decoration: none; }
"""
    parts = [f"<!doctype html><html><head><meta charset='utf-8'><title>{e(idn['name'])} — {e(t['job']['title'])}</title><style>{css}</style></head><body>"]
    parts.append(f"<h1>{e(idn['name'])}</h1>")
    parts.append(f"<div class='headline'>{e(t['headline'])}</div>")
    parts.append(
        "<div class='contact'>"
        + " &nbsp;|&nbsp; ".join(
            [
                e(idn["location"]),
                e(idn["phone"]),
                e(idn["email"]),
                "<a href='https://www.chinola.app'>chinola.app</a>",
                "<a href='https://github.com/r8s11'>github.com/r8s11</a>",
                "<a href='https://www.linkedin.com/in/rooseveltbsegura'>linkedin.com/in/rooseveltbsegura</a>",
            ]
        )
        + "</div>"
    )

    parts.append("<h2>Professional Summary</h2>")
    parts.append(f"<p class='summary'>{e(t['summary'])}</p>")

    parts.append("<h2>Certifications</h2>")
    for c in b["certifications"]:
        parts.append(f"<p class='cert'><strong>{e(c['name'])}</strong> — {e(c['issuer'])} ({e(c['date'])})</p>")

    parts.append("<h2>Technical Skills</h2><table class='skills'>")
    for cat, items in rows:
        parts.append(f"<tr><td class='cat'>{e(cat)}</td><td>{e(items)}</td></tr>")
    parts.append("</table>")

    parts.append("<h2>Professional Experience</h2>")
    for role in t["experience"]:
        parts.append("<div class='role'>")
        parts.append(f"<p class='role-title'>{e(role['title'])}</p>")
        parts.append(
            f"<p class='role-meta'>{e(role['employer'])} — {e(role['location'])}"
            f" <span class='dates'>&nbsp;|&nbsp; {e(role['dates'])}</span></p>"
        )
        parts.append("<ul>")
        for bullet in role["bullets"]:
            lead, rest = bullet_parts(bullet["text"], bullet.get("bold_lead"))
            if lead:
                parts.append(f"<li><strong>{e(lead)}</strong>{e(rest)}</li>")
            else:
                parts.append(f"<li>{e(bullet['text'])}</li>")
        parts.append("</ul></div>")

    mil = t["military_service"]
    parts.append("<h2>Military Service</h2><div class='role'>")
    parts.append(f"<p class='role-title'>{e(mil['title'])}</p>")
    parts.append(
        f"<p class='role-meta'>{e(mil['organization'])} — {e(mil['location'])}"
        f" <span class='dates'>&nbsp;|&nbsp; {e(mil['dates'])}</span></p>"
    )
    parts.append("<ul>")
    for text in mil["bullets"]:
        parts.append(f"<li>{e(text)}</li>")
    parts.append("</ul></div>")

    parts.append("</body></html>")
    Path(path).write_text("\n".join(parts))


def main():
    tailored, base, out = sys.argv[1], sys.argv[2], sys.argv[3]
    t, b, rows = load(tailored, base)
    build_docx(t, b, rows, out + ".docx")
    build_html(t, b, rows, out + ".html")
    print("wrote", out + ".docx", "and", out + ".html")


if __name__ == "__main__":
    main()
