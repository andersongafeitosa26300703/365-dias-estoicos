"""Reel narrado do carrossel: a voz le as 5 laminas e o video troca de lamina no ritmo da fala.

Roteiro lido (uma lamina por trecho, separados por pausa longa): gancho; citacao e autor; "O que significa" + reflexao;
"No trabalho" + aplicacao; chamada final. O video e vertical (1080x1920) com a lamina do carrossel (1080x1350) no centro.
So vale para dias com gancho (`hook`), que sao os dias com carrossel; os demais continuam com o narrado curto.

Uso local (com um mp3 ja gravado): python scripts/narracao.py --dia 57 --audio voz.mp3 --forcar
"""
import re
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

ATRASO = 0.4   # silencio antes da fala, em segundos (o mesmo do narrado curto)
FADE = 0.4     # duracao da troca de lamina
CAPA_MS = 2000  # capa do Reel: a lamina do gancho
CTA = "Envie para quem precisa ler isto hoje. Salve para reler. Siga o 365 dias estoicos."


def usa_formato(entry):
    return bool(entry.get("hook"))


def texto_carrossel(entry):
    """Texto enviado a voz. As marcacoes entre colchetes dao ritmo e pausas e nao sao lidas."""
    gancho = " ".join(p for p in (entry["hook"].strip(), (entry.get("hook2") or "").strip()) if p)
    partes = [
        f"[slowly] [mysterious] {gancho}", "[long pause]",
        f"“{entry['quote']}” {entry['author']}.", "[long pause]",
        f"[slowly] O que significa. {entry['reflection']}", "[long pause]",
    ]
    if entry.get("apply"):
        partes += [f"[slowly] No trabalho… {entry['apply']}", "[long pause]"]
    partes.append(CTA)
    return " ".join(partes)


def _duracao(arquivo):
    return float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(arquivo)],
                                capture_output=True, text=True, check=True).stdout)


def inicios_das_laminas(audio, entry, n):
    """Instante (s, no video, ja com o atraso) em que cada lamina entra. n = quantidade de laminas."""
    dur = _duracao(audio)
    saida = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(audio), "-af", "silencedetect=noise=-38dB:d=0.6", "-f", "null", "-"],
                           capture_output=True, text=True).stderr
    inicios = [float(x) for x in re.findall(r"silence_start: ([\d.]+)", saida)]
    fins = [(float(e), float(d)) for e, d in re.findall(r"silence_end: ([\d.]+) \| silence_duration: ([\d.]+)", saida)]
    pausas = [(ini, fim, dp) for ini, (fim, dp) in zip(inicios, fins)]

    # Reserva: proporcional ao tamanho do texto de cada lamina
    pesos = [len(x) for x in _blocos(entry)]
    total = sum(pesos)
    prop, acc = [0.0], 0
    for p in pesos[:-1]:
        acc += p
        prop.append(ATRASO + dur * acc / total)

    # Para cada troca de lamina, escolhe a MAIOR pausa que termina perto do instante esperado pela divisao proporcional.
    # (O tamanho da pausa varia de uma geracao para outra; so a posicao aproximada e confiavel.)
    det = [0.0]
    for k in range(1, n):
        perto = [p for p in pausas if abs(ATRASO + p[1] - prop[k]) < 3.5 and p[1] > det[-1] + 1.0]
        if not perto:
            det = None
            break
        det.append(ATRASO + max(perto, key=lambda p: p[2])[1] - 0.2)
    if det and all(b - a > 1.5 for a, b in zip(det, det[1:])):
        return det
    print("[tempos] pausas nao identificadas; usando divisao proporcional")
    return prop


def _blocos(entry):
    """Texto de cada lamina, na ordem em que e lido."""
    gancho = " ".join(p for p in (entry["hook"].strip(), (entry.get("hook2") or "").strip()) if p)
    blocos = [gancho, f"“{entry['quote']}” {entry['author']}.", f"O que significa. {entry['reflection']}"]
    if entry.get("apply"):
        blocos.append(f"No trabalho… {entry['apply']}")
    blocos.append(CTA)
    return blocos


def reel_carrossel(entry, audio, destino):
    """Monta o MP4. Devolve (caminho, duracao_s)."""
    import carrossel as car
    from PIL import Image

    orig = car.centered

    def sem_arraste(d, y, texto, *a, **k):  # o "ARRASTE →" da 1a lamina nao faz sentido num video
        if str(texto).strip().startswith("ARRASTE"):
            return None
        return orig(d, y, texto, *a, **k)

    car.centered = sem_arraste
    try:
        with tempfile.TemporaryDirectory() as tmp:
            laminas = car.render_carrossel(entry, Path(tmp), "lamina")
            n = len(laminas)
            ini = inicios_das_laminas(audio, entry, n)
            total = _duracao(audio) + ATRASO + 1.0
            segs = [ini[i + 1] - ini[i] for i in range(n - 1)] + [total - ini[-1]]

            cmd = ["ffmpeg", "-v", "error", "-y"]
            filtros = []
            for i, lam in enumerate(laminas):
                cor = "0x%02x%02x%02x" % Image.open(lam).convert("RGB").getpixel((4, 4))
                d = segs[i] + (FADE if i < n - 1 else 0)
                cmd += ["-loop", "1", "-framerate", "30", "-t", f"{d:.3f}", "-i", str(lam)]
                filtros.append(f"[{i}:v]scale=1080:1350,pad=1080:1920:0:285:color={cor},format=yuv420p,setsar=1[v{i}]")
            ult = "v0"
            for k in range(1, n):
                filtros.append(f"[{ult}][v{k}]xfade=transition=fade:duration={FADE}:offset={ini[k]:.3f}[x{k}]")
                ult = f"x{k}"
            Path(destino).parent.mkdir(parents=True, exist_ok=True)
            cmd += ["-i", str(audio), "-filter_complex", ";".join(filtros), "-map", f"[{ult}]", "-map", f"{n}:a",
                    "-af", f"adelay={int(ATRASO * 1000)}|{int(ATRASO * 1000)},apad=pad_dur=1",
                    "-c:v", "libx264", "-crf", "23", "-preset", "medium", "-pix_fmt", "yuv420p",
                    "-c:a", "aac", "-b:a", "160k", "-shortest", "-movflags", "+faststart", str(destino)]
            r = subprocess.run(cmd, capture_output=True, text=True)
            if r.returncode != 0:
                raise RuntimeError(f"ffmpeg falhou: {r.stderr[-400:]}")
    finally:
        car.centered = orig
    return Path(destino), _duracao(destino)
