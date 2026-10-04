"""Gera o logo (foto de perfil) 1080x1080 no mesmo estilo dos posts: fundo escuro, dourado, EB Garamond."""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
S = 1080
BG = (20, 17, 15)
GOLD = (201, 169, 110)
SOFT = (238, 232, 220)

serif = ROOT / "fonts" / "serif.ttf"
italic = ROOT / "fonts" / "serif-italic.ttf"


def centered(d, cy, text, font, fill, spacing=0):
    if spacing:
        widths = [d.textlength(c, font=font) for c in text]
        total = sum(widths) + spacing * (len(text) - 1)
        x = (S - total) / 2
        for c, w in zip(text, widths):
            d.text((x, cy), c, font=font, fill=fill, anchor="ls")
            x += w + spacing
    else:
        d.text((S / 2, cy), text, font=font, fill=fill, anchor="ms")


img = Image.new("RGB", (S, S), BG)
d = ImageDraw.Draw(img)

# Aros concentricos (tudo fica dentro do recorte circular do Instagram)
c = S / 2
for r, w in ((500, 6), (478, 2)):
    d.ellipse([c - r, c - r, c + r, c + r], outline=GOLD, width=w)

# Numero 365
big = ImageFont.truetype(str(serif), 330)
centered(d, 600, "365", big, SOFT)

# Filete e nome
d.line([(c - 150, 650), (c + 150, 650)], fill=GOLD, width=3)
name = ImageFont.truetype(str(serif), 66)
centered(d, 735, "DIAS ESTOICOS", name, GOLD, spacing=10)

# Coluna dorica estilizada acima do numero
top, bot = 190, 330
d.rectangle([c - 70, top, c + 70, top + 14], fill=GOLD)             # capitel
d.rectangle([c - 54, top + 14, c + 54, top + 28], fill=GOLD)
for dx in (-34, -11, 12, 35):                                       # caneluras do fuste
    d.line([(c + dx, top + 34), (c + dx, bot - 20)], fill=GOLD, width=5)
d.rectangle([c - 54, bot - 20, c + 54, bot - 8], fill=GOLD)         # base
d.rectangle([c - 70, bot - 8, c + 70, bot + 6], fill=GOLD)

small = ImageFont.truetype(str(italic), 44)
centered(d, 830, "uma lição por dia", small, SOFT)

out = ROOT / "assets"
out.mkdir(exist_ok=True)
img.save(out / "logo.png")
print(out / "logo.png")
