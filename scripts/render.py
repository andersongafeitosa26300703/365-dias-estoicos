"""Gera a imagem 1080x1350 do post do dia a partir de uma entrada do calendario."""
import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
W, H = 1080, 1350

THEMES = {
    "dark": dict(bg=(20, 17, 15), accent=(201, 169, 110), text=(238, 232, 220), muted=(140, 130, 115)),
    "light": dict(bg=(244, 239, 228), accent=(140, 104, 48), text=(34, 29, 24), muted=(120, 110, 95)),
}

HANDLE = "@365diasestoicos"

# Fonte do projeto primeiro (necessaria no GitHub Actions); Georgia so serve para teste local no Windows.
FONT_CANDIDATES = [
    ROOT / "fonts" / "serif.ttf",
    Path("C:/Windows/Fonts/georgia.ttf"),
]
FONT_ITALIC_CANDIDATES = [
    ROOT / "fonts" / "serif-italic.ttf",
    Path("C:/Windows/Fonts/georgiai.ttf"),
]


def load_font(candidates, size):
    for path in candidates:
        if path.exists():
            return ImageFont.truetype(str(path), size)
    raise FileNotFoundError(f"Nenhuma fonte encontrada em: {candidates}")


def wrap(draw, text, font, max_width):
    lines, current = [], ""
    for word in text.split():
        trial = f"{current} {word}".strip()
        if draw.textlength(trial, font=font) <= max_width:
            current = trial
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def centered(draw, y, text, font, fill):
    w = draw.textlength(text, font=font)
    draw.text(((W - w) / 2, y), text, font=font, fill=fill)


def render(entry, out_path):
    # dias impares: fundo escuro; pares: fundo claro (grade alternada, como os perfis grandes do nicho)
    t = THEMES["dark" if entry["day"] % 2 else "light"]
    BG, GOLD, TEXT, MUTED = t["bg"], t["accent"], t["text"], t["muted"]
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)

    margin = 110
    max_w = W - 2 * margin

    # Moldura fina
    d.rectangle([40, 40, W - 40, H - 40], outline=GOLD, width=2)

    # Cabecalho
    head = load_font(FONT_CANDIDATES, 30)
    centered(d, 120, "365 DIAS ESTOICOS", head, GOLD)
    d.line([(W / 2 - 40, 185), (W / 2 + 40, 185)], fill=GOLD, width=2)

    # Citacao: maior fonte que caiba na area util
    quote = f"\u201c{entry['quote']}\u201d"
    top, bottom = 270, 1050
    for size in range(76, 38, -2):
        qf = load_font(FONT_ITALIC_CANDIDATES, size)
        lines = wrap(d, quote, qf, max_w)
        line_h = int(size * 1.35)
        if len(lines) * line_h <= bottom - top:
            break
    block_h = len(lines) * line_h
    y = top + ((bottom - top) - block_h) / 2
    for line in lines:
        centered(d, y, line, qf, TEXT)
        y += line_h

    # Autor
    d.line([(W / 2 - 40, 1090), (W / 2 + 40, 1090)], fill=GOLD, width=2)
    af = load_font(FONT_CANDIDATES, 38)
    centered(d, 1120, entry["author"].upper(), af, GOLD)

    # Rodape
    hf = load_font(FONT_CANDIDATES, 26)
    centered(d, H - 110, HANDLE, hf, MUTED)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path, "JPEG", quality=95)
    return out_path


SW, SH = 1080, 1920


def render_story(entry, out_path):
    """Versao vertical 1080x1920 para Stories. Zona segura: o Instagram cobre ~250px no topo e na base."""
    t = THEMES["dark" if entry["day"] % 2 else "light"]
    BG, GOLD, TEXT, MUTED = t["bg"], t["accent"], t["text"], t["muted"]
    img = Image.new("RGB", (SW, SH), BG)
    d = ImageDraw.Draw(img)
    margin = 100
    max_w = SW - 2 * margin

    d.rectangle([40, 40, SW - 40, SH - 40], outline=GOLD, width=2)

    head = load_font(FONT_CANDIDATES, 36)
    centered(d, 330, "365 DIAS ESTOICOS", head, GOLD)
    d.line([(SW / 2 - 50, 400), (SW / 2 + 50, 400)], fill=GOLD, width=2)

    quote = f"“{entry['quote']}”"
    top, bottom = 470, 1330
    for size in range(96, 44, -2):
        qf = load_font(FONT_ITALIC_CANDIDATES, size)
        lines = wrap(d, quote, qf, max_w)
        line_h = int(size * 1.35)
        if len(lines) * line_h <= bottom - top:
            break
    y = top + ((bottom - top) - len(lines) * line_h) / 2
    for line in lines:
        centered(d, y, line, qf, TEXT)
        y += line_h

    d.line([(SW / 2 - 50, 1420), (SW / 2 + 50, 1420)], fill=GOLD, width=2)
    af = load_font(FONT_CANDIDATES, 46)
    centered(d, 1460, entry["author"].upper(), af, GOLD)
    hf = load_font(FONT_CANDIDATES, 32)
    centered(d, 1600, HANDLE, hf, MUTED)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path, "JPEG", quality=95)
    return out_path


if __name__ == "__main__":
    day = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    entries = json.loads((ROOT / "data" / "calendar.json").read_text(encoding="utf-8"))
    entry = next(e for e in entries if e["day"] == day)
    print(render(entry, ROOT / "output" / f"dia-{day:03d}.jpg"))
