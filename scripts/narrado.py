"""Gera um vídeo narrado (MP4 1080x1920): imagem de fundo animada, chuva desenhada, texto sincronizado com a voz e um som ambiente baixo.

A voz vem pronta (mp3); o texto entra nos instantes passados em `tempos`, medidos nas pausas da fala.
Requer ffmpeg, Pillow e numpy.

Uso: python scripts/narrado.py DIA VOZ.mp3 FUNDO.png SAIDA.mp4 quote=0.5 label=5.9 apply=7.1
"""
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from reel import FPS, ROOT, SH, SW, SONS_DIR, _aplica, _camadas


def _chuva(duracao, semente=7, gotas=170):
    """Gerador de quadros RGBA com riscos de chuva finos e discretos."""
    rng = np.random.default_rng(semente)
    x = rng.uniform(0, SW, gotas)
    y = rng.uniform(0, SH, gotas)
    comp = rng.uniform(40, 120, gotas)
    vel = rng.uniform(1100, 1900, gotas)  # px/s
    alfa = rng.integers(35, 90, gotas)
    for n in range(int(duracao * FPS)):
        im = Image.new("RGBA", (SW, SH), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        for i in range(gotas):
            d.line([(x[i], y[i]), (x[i] - comp[i] * 0.12, y[i] + comp[i])], fill=(205, 220, 228, int(alfa[i])), width=2 if comp[i] > 90 else 1)
        yield im
        y += vel / FPS
        x -= vel / FPS * 0.12
        saiu = y > SH
        y[saiu] = -comp[saiu]
        x[saiu] = rng.uniform(0, SW + 150, saiu.sum())


def narrado(entry, voz, fundo_img, saida, tempos, atraso=0.4, cauda=1.6, som="chuva"):
    voz, fundo_img, saida = Path(voz), Path(fundo_img), Path(saida)
    saida.parent.mkdir(parents=True, exist_ok=True)
    dur_voz = float(subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(voz)],
        capture_output=True, text=True, check=True).stdout)
    total = atraso + dur_voz + cauda
    tempos = {**tempos, "fim": total}
    base, camadas, _, _ = _camadas(entry, tempos=tempos, fundo=False, tema="dark")
    n_quadros = int(total * FPS)

    # Fundo: a imagem (qualquer proporcao) cobre a altura e a janela vertical desliza devagar da esquerda para a direita;
    # um leve desfoque disfarca a ampliacao.
    fundo = (
        f"[0:v]scale=-2:2000,crop=1080:1920:x='(iw-1080)*(0.25+0.5*t/{total:.2f})':y='(ih-1920)/2',"
        f"gblur=sigma=1.6,eq=brightness=0.04:contrast=1.08:saturation=0.9,vignette=PI/6[bg];[bg][1:v]overlay=shortest=1[v]"
    )
    bed = SONS_DIR / f"{som}.m4a"
    if bed.exists():
        audio = (
            f"[2:a]loudnorm=I=-16:TP=-1.5:LRA=11,aformat=channel_layouts=stereo,adelay={int(atraso*1000)}|{int(atraso*1000)},apad[voz];"
            f"[3:a]volume=0.5,afade=t=in:d=1.0,afade=t=out:st={max(0.0, total-1.6):.2f}:d=1.6[bed];"
            f"[voz][bed]amix=inputs=2:duration=longest:normalize=0,atrim=0:{total:.2f}[a]"
        )
        entradas_bed = ["-ss", "3", "-t", f"{total:.2f}", "-i", str(bed)]
    else:
        audio = f"[2:a]loudnorm=I=-16:TP=-1.5:LRA=11,aformat=channel_layouts=stereo,adelay={int(atraso*1000)}|{int(atraso*1000)},apad,atrim=0:{total:.2f}[a]"
        entradas_bed = []
    cmd = [
        "ffmpeg", "-y", "-loglevel", "error",
        "-loop", "1", "-framerate", str(FPS), "-i", str(fundo_img),
        "-f", "rawvideo", "-pix_fmt", "rgba", "-s", f"{SW}x{SH}", "-r", str(FPS), "-i", "-",
        "-i", str(voz), *entradas_bed,
        "-filter_complex", fundo + ";" + audio,
        "-map", "[v]", "-map", "[a]", "-t", f"{total:.2f}",
        "-c:v", "libx264", "-preset", "medium", "-crf", "23", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", str(saida),
    ]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for n, chuva in zip(range(n_quadros), _chuva(total)):
        texto, _ = _aplica(base, camadas, n / FPS)
        chuva.alpha_composite(texto)
        proc.stdin.write(chuva.tobytes())
    proc.stdin.close()
    if proc.wait() != 0:
        raise RuntimeError("ffmpeg falhou ao montar o video narrado")
    return saida, total


if __name__ == "__main__":
    dia, voz, fundo_img, saida = int(sys.argv[1]), sys.argv[2], sys.argv[3], sys.argv[4]
    tempos = {k: float(v) for k, v in (a.split("=") for a in sys.argv[5:])}
    entry = next(e for e in json.loads((ROOT / "data" / "calendar.json").read_text(encoding="utf-8")) if e["day"] == dia)
    print(narrado(entry, voz, fundo_img, saida, tempos))
