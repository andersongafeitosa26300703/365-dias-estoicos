"""Gera o Reel (MP4 1080x1920, sem som) de uma citacao: cabecalho, citacao, autor e 'No trabalho' entram um a um.

Usa o mesmo layout do Story (render.py). O tempo de cada etapa cresce com o tamanho do texto, para dar tempo de ler.
Requer ffmpeg instalado.

Uso: python scripts/reel.py DIA [SAIDA.mp4]
"""
import json
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw

from render import (FONT_CANDIDATES, FONT_ITALIC_CANDIDATES, HANDLE, ROOT, SH, SW, THEMES, centered, fit_block,
                    load_font, spaced, wrap)

FPS = 30


def _camadas(entry):
    """Devolve (base, camadas, fim, instante_da_capa). Cada camada e (imagem RGBA do quadro, instante de entrada em s)."""
    t = THEMES["dark" if entry["day"] % 2 else "light"]
    BG, GOLD, TEXT, MUTED = t["bg"], t["accent"], t["text"], t["muted"]
    tmp = ImageDraw.Draw(Image.new("RGB", (SW, SH)))
    max_w = SW - 2 * 100
    tem_apply = bool(entry.get("apply"))
    quote = f"“{entry['quote']}”"
    original = entry.get("original")

    def nova():
        im = Image.new("RGBA", (SW, SH), (0, 0, 0, 0))
        return im, ImageDraw.Draw(im)

    base = Image.new("RGBA", (SW, SH), BG + (255,))
    bd = ImageDraw.Draw(base)
    bd.rectangle([40, 40, SW - 40, SH - 40], outline=GOLD, width=2)

    camadas = []
    # cabecalho
    im, d = nova()
    head_y = 300 if tem_apply else 330
    centered(d, head_y, "365 DIAS ESTOICOS", load_font(FONT_CANDIDATES, 34 if tem_apply else 36), GOLD)
    line_y = head_y + 65 if tem_apply else head_y + 70
    d.line([(SW / 2 - 50, line_y), (SW / 2 + 50, line_y)], fill=GOLD, width=2)
    camadas.append((im, 0.2))

    # geometria da citacao (identica a do Story)
    if tem_apply and original:
        of, olines, olh = fit_block(tmp, original, FONT_ITALIC_CANDIDATES, max_w, 200, 50, 30, spacing=1.3)
        qf, qlines, qlh = fit_block(tmp, quote, FONT_ITALIC_CANDIDATES, max_w, 340, 70, 36, spacing=1.32)
        q_top, q_bottom = 630, 960
    elif tem_apply:
        qf, qlines, qlh = fit_block(tmp, quote, FONT_ITALIC_CANDIDATES, max_w, 520, 82, 40, spacing=1.32)
        q_top, q_bottom = 420, 960
    else:
        qlines, qf, qlh = None, None, None
        for size in range(96, 44, -2):
            qf = load_font(FONT_ITALIC_CANDIDATES, size)
            qlines = wrap(tmp, quote, qf, max_w)
            qlh = int(size * 1.35)
            if len(qlines) * qlh <= 1330 - 470:
                break
        q_top, q_bottom = 470, 1330

    inicio = 0.8
    if tem_apply and original:
        im, d = nova()
        y = 410 + (200 - len(olines) * olh) / 2
        for ln in olines:
            centered(d, y, ln, of, GOLD)
            y += olh
        camadas.append((im, inicio))
        inicio = 2.2
    im, d = nova()
    y = q_top + ((q_bottom - q_top) - len(qlines) * qlh) / 2
    for ln in qlines:
        centered(d, y, ln, qf, TEXT)
        y += qlh
    camadas.append((im, inicio))
    t_quote = inicio

    # autor (e referencia, quando houver)
    label = entry["author"].upper() + (f" · {entry['ref'].upper()}" if entry.get("ref") else "")
    size0, size1 = (38, 26) if tem_apply else (46, 30)
    lf = load_font(FONT_CANDIDATES, size0)
    for size in range(size0, size1, -2):
        lf = load_font(FONT_CANDIDATES, size)
        if tmp.textlength(label, font=lf) <= max_w:
            break
    im, d = nova()
    if tem_apply:
        centered(d, 985, label, lf, GOLD)
    else:
        d.line([(SW / 2 - 50, 1420), (SW / 2 + 50, 1420)], fill=GOLD, width=2)
        centered(d, 1460, label, lf, GOLD)
    t_label = t_quote + max(2.6, len(entry["quote"]) / 17)
    camadas.append((im, t_label))
    fim = t_label + 3.5

    # complemento "No trabalho"
    if tem_apply:
        af, alines, alh = fit_block(tmp, entry["apply"], FONT_CANDIDATES, max_w - 20, 330, 56, 34, spacing=1.38)
        im, d = nova()
        d.line([(SW / 2 - 60, 1090), (SW / 2 + 60, 1090)], fill=GOLD, width=2)
        spaced(d, 1125, "NO TRABALHO", load_font(FONT_CANDIDATES, 30), GOLD, 8)
        y = 1190 + (340 - len(alines) * alh) / 2
        for ln in alines:
            centered(d, y, ln, af, TEXT)
            y += alh
        t_apply = t_label + 1.8
        camadas.append((im, t_apply))
        fim = t_apply + max(4.2, len(entry["apply"]) / 15) + 1.0

    # perfil, sempre visivel
    centered(bd, 1640 if tem_apply else 1600, HANDLE, load_font(FONT_CANDIDATES, 30 if tem_apply else 32), MUTED)
    return base, camadas, fim, max(0.0, fim - 1.0)


def _aplica(base, camadas, t):
    frame = base.copy()
    chave = []
    for im, inicio in camadas:
        p = min(1.0, max(0.0, (t - inicio) / 0.7))
        chave.append(round(p, 3))
        if p <= 0:
            continue
        e = 1 - (1 - p) ** 3  # entrada suave
        camada = im
        if p < 1:
            camada = im.copy()
            camada.putalpha(camada.getchannel("A").point(lambda v, e=e: int(v * e)))
        frame.alpha_composite(camada, dest=(0, int((1 - e) * 26)))
    return frame, tuple(chave)


def reel(entry, out_path):
    """Grava o MP4 e devolve (caminho, duracao em s, instante sugerido para a capa em ms)."""
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    base, camadas, fim, capa = _camadas(entry)
    cmd = [
        "ffmpeg", "-y", "-loglevel", "error",
        "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{SW}x{SH}", "-r", str(FPS), "-i", "-",
        "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=44100",
        "-shortest", "-c:v", "libx264", "-preset", "medium", "-crf", "22", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "64k", "-movflags", "+faststart", str(out_path),
    ]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    ultima_chave, ultimos_bytes = None, None
    for n in range(int(fim * FPS)):
        frame, chave = _aplica(base, camadas, n / FPS)
        if chave != ultima_chave:  # quadros parados nao precisam ser recompostos
            ultimos_bytes, ultima_chave = frame.convert("RGB").tobytes(), chave
        proc.stdin.write(ultimos_bytes)
    proc.stdin.close()
    if proc.wait() != 0:
        raise RuntimeError("ffmpeg falhou ao gerar o Reel")
    return out_path, fim, int(capa * 1000)


if __name__ == "__main__":
    dia = int(sys.argv[1])
    entry = next(e for e in json.loads((ROOT / "data" / "calendar.json").read_text(encoding="utf-8")) if e["day"] == dia)
    destino = Path(sys.argv[2]) if len(sys.argv) > 2 else ROOT / "output" / f"reel-{dia:03d}.mp4"
    print(reel(entry, destino))
