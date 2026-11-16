"""Gera as 5 laminas (1080x1350) do carrossel do dia: gancho, frase, significado, no trabalho e chamada final.

Precisa de entry["hook"] (e, se houver, entry["hook2"]). Mesmas cores do post: dia impar escuro, dia par claro.

Uso: python scripts/carrossel.py DIA [PASTA_DE_SAIDA]
"""
import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw

from render import FONT_CANDIDATES, FONT_ITALIC_CANDIDATES, H, HANDLE, ROOT, THEMES, W, centered, fit_block, load_font, spaced

LAMINAS = 5


def _base(entry, i, rotulo=None):
    t = THEMES["dark" if entry["day"] % 2 else "light"]
    img = Image.new("RGB", (W, H), t["bg"])
    d = ImageDraw.Draw(img)
    d.rectangle([40, 40, W - 40, H - 40], outline=t["accent"], width=2)
    centered(d, 100, "365 DIAS ESTOICOS", load_font(FONT_CANDIDATES, 28), t["accent"])
    if rotulo:
        spaced(d, 250, rotulo, load_font(FONT_CANDIDATES, 26), t["accent"], 7)
        d.line([(W / 2 - 50, 305), (W / 2 + 50, 305)], fill=t["accent"], width=2)
    # progresso: quantas laminas ha e onde o leitor esta
    apagado = tuple(int(a * 0.3 + b * 0.7) for a, b in zip(t["accent"], t["bg"]))
    x0 = W / 2 - (LAMINAS * 34 - 14) / 2
    for k in range(LAMINAS):
        d.rounded_rectangle([x0 + k * 34, H - 150, x0 + k * 34 + 20, H - 144], radius=3, fill=t["accent"] if k == i else apagado)
    centered(d, H - 115, HANDLE, load_font(FONT_CANDIDATES, 26), t["muted"])
    return img, d, t


def _bloco(d, texto, cands, y, cor, max_h, start, stop, max_w=860, spacing=1.2):
    f, linhas, lh = fit_block(d, texto, cands, max_w, max_h, start, stop, spacing=spacing)
    for ln in linhas:
        centered(d, y, ln, f, cor)
        y += lh
    return y


def render_carrossel(entry, pasta, prefixo):
    """Grava prefixo-1.jpg ... prefixo-5.jpg em `pasta` e devolve a lista de caminhos."""
    pasta = Path(pasta)
    pasta.mkdir(parents=True, exist_ok=True)
    saidas = []

    def salva(img, k):
        p = pasta / f"{prefixo}-{k}.jpg"
        img.save(p, "JPEG", quality=95)
        saidas.append(p)

    # 1) Gancho (chamada do perfil, nao e citacao)
    img, d, t = _base(entry, 0)
    y = _bloco(d, entry["hook"], FONT_CANDIDATES, 400, t["text"], 330, 92, 60)
    if entry.get("hook2"):
        y = _bloco(d, entry["hook2"], FONT_ITALIC_CANDIDATES, y + 14, t["accent"], 230, 92, 60)
    centered(d, H - 230, "ARRASTE  →", load_font(FONT_CANDIDATES, 30), t["accent"])
    salva(img, 1)

    # 2) A frase
    img, d, t = _base(entry, 1, "A FRASE")
    y = _bloco(d, f"“{entry['quote']}”", FONT_ITALIC_CANDIDATES, 400, t["text"], 520, 84, 46, spacing=1.32)
    d.line([(W / 2 - 40, y + 44), (W / 2 + 40, y + 44)], fill=t["accent"], width=2)
    centered(d, y + 74, entry["author"].upper(), load_font(FONT_CANDIDATES, 38), t["accent"])
    salva(img, 2)

    # 3) O que significa
    img, d, t = _base(entry, 2, "O QUE SIGNIFICA")
    _bloco(d, entry["reflection"], FONT_CANDIDATES, 400, t["text"], 700, 60, 36, spacing=1.38)
    salva(img, 3)

    # 4) No trabalho (quando houver)
    img, d, t = _base(entry, 3, "NO TRABALHO, HOJE" if entry.get("apply") else "PARA HOJE")
    _bloco(d, entry.get("apply") or entry["reflection"], FONT_CANDIDATES, 420, t["text"], 640, 64, 38, spacing=1.38)
    salva(img, 4)

    # 5) Chamada final
    img, d, t = _base(entry, 4, "ANTES DE SAIR")
    y = _bloco(d, "Envie para quem precisa ler isto hoje.", FONT_CANDIDATES, 400, t["text"], 260, 64, 48, max_w=800)
    y = _bloco(d, "Salve para reler quando precisar.", FONT_CANDIDATES, y + 50, t["muted"], 130, 44, 36, max_w=760)
    d.line([(W / 2 - 50, y + 50), (W / 2 + 50, y + 50)], fill=t["accent"], width=2)
    _bloco(d, f"Siga {HANDLE}: uma ideia estoica por dia, aplicada ao trabalho.", FONT_ITALIC_CANDIDATES, y + 90, t["accent"], 200, 44, 34, max_w=780)
    salva(img, 5)
    return saidas


if __name__ == "__main__":
    dia = int(sys.argv[1])
    entry = next(e for e in json.loads((ROOT / "data" / "calendar.json").read_text(encoding="utf-8")) if e["day"] == dia)
    entry.setdefault("hook", "Gancho de teste para o dia.")
    print(render_carrossel(entry, sys.argv[2] if len(sys.argv) > 2 else ROOT / "output", f"dia-{dia:03d}"))
