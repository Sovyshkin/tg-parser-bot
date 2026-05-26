from pathlib import Path
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, ListFlowable, ListItem, Preformatted

src = Path('README.md')
out = Path('README.pdf')

font_regular = '/System/Library/Fonts/Supplemental/Arial Unicode.ttf'
font_bold = '/System/Library/Fonts/Supplemental/Arial Bold.ttf'

pdfmetrics.registerFont(TTFont('BodyFont', font_regular))
pdfmetrics.registerFont(TTFont('BodyFontBold', font_bold))

styles = getSampleStyleSheet()
styles.add(ParagraphStyle(
    name='Body',
    fontName='BodyFont',
    fontSize=10.5,
    leading=14,
    spaceAfter=6,
))
styles.add(ParagraphStyle(
    name='H1',
    parent=styles['Heading1'],
    fontName='BodyFontBold',
    fontSize=20,
    leading=24,
    textColor=colors.HexColor('#111827'),
    spaceAfter=10,
))
styles.add(ParagraphStyle(
    name='H2',
    parent=styles['Heading2'],
    fontName='BodyFontBold',
    fontSize=14,
    leading=18,
    textColor=colors.HexColor('#1f2937'),
    spaceBefore=8,
    spaceAfter=6,
))
styles.add(ParagraphStyle(
    name='Code',
    fontName='Courier',
    fontSize=9,
    leading=12,
    backColor=colors.HexColor('#f3f4f6'),
    borderColor=colors.HexColor('#e5e7eb'),
    borderWidth=0.5,
    borderPadding=6,
    borderRadius=3,
    spaceAfter=8,
))

story = []
lines = src.read_text(encoding='utf-8').splitlines()

in_code = False
code_buf = []
bullet_buf = []
num_buf = []

def flush_bullets():
    global bullet_buf
    if bullet_buf:
        items = [ListItem(Paragraph(item, styles['Body'])) for item in bullet_buf]
        story.append(ListFlowable(items, bulletType='bullet', start='•', leftIndent=12))
        story.append(Spacer(1, 2))
        bullet_buf = []

def flush_nums():
    global num_buf
    if num_buf:
        items = [ListItem(Paragraph(item, styles['Body'])) for item in num_buf]
        story.append(ListFlowable(items, bulletType='1', leftIndent=12))
        story.append(Spacer(1, 2))
        num_buf = []

for raw in lines:
    line = raw.rstrip('\n')

    if line.strip().startswith('```'):
        flush_bullets(); flush_nums()
        if not in_code:
            in_code = True
            code_buf = []
        else:
            in_code = False
            story.append(Preformatted('\n'.join(code_buf), styles['Code']))
            code_buf = []
        continue

    if in_code:
        code_buf.append(line)
        continue

    if not line.strip():
        flush_bullets(); flush_nums()
        story.append(Spacer(1, 4))
        continue

    if line.startswith('# '):
        flush_bullets(); flush_nums()
        story.append(Paragraph(line[2:].strip(), styles['H1']))
        continue
    if line.startswith('## '):
        flush_bullets(); flush_nums()
        story.append(Paragraph(line[3:].strip(), styles['H2']))
        continue

    stripped = line.strip()
    if stripped.startswith('- '):
        flush_nums()
        bullet_buf.append(stripped[2:].strip())
        continue

    parts = stripped.split('. ', 1)
    if len(parts) == 2 and parts[0].isdigit():
        flush_bullets()
        num_buf.append(parts[1].strip())
        continue

    flush_bullets(); flush_nums()
    text = (
        line.replace('&', '&amp;')
            .replace('<', '&lt;')
            .replace('>', '&gt;')
            .replace('`', '')
    )
    story.append(Paragraph(text, styles['Body']))

flush_bullets(); flush_nums()

doc = SimpleDocTemplate(
    str(out),
    pagesize=A4,
    leftMargin=18*mm,
    rightMargin=18*mm,
    topMargin=16*mm,
    bottomMargin=16*mm,
    title='TG Parsing Bot - Инструкция',
)
doc.build(story)
print('README.pdf styled')
