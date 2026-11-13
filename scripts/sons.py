"""Sintetiza os sons de fundo dos Reels (chuva, mata, calmo) em assets/sons/*.m4a.

Sao sons originais, gerados por codigo (sem gravacoes de terceiros, entao sem direitos autorais a conferir).
Cada arquivo tem 45 s, maior que o Reel mais longo, e o Reel usa um trecho que muda de acordo com o dia.
Precisa de numpy e ffmpeg (so para gerar; o workflow diario usa apenas os arquivos prontos).

Uso: python scripts/sons.py
"""
import subprocess
import wave
from pathlib import Path

import numpy as np

SR = 44100
SEG = 45
N = SR * SEG
SAIDA = Path(__file__).resolve().parent.parent / "assets" / "sons"
ALVO_RMS_DB = -24.0  # fundo suave: o texto e o protagonista, nao o som


def filtro(x, lo=None, hi=None, inclinacao=0.0):
    """Passa-faixa por FFT (bordas suaves). `inclinacao` > 0 deixa o espectro mais grave (tipo ruido rosa)."""
    X = np.fft.rfft(x)
    f = np.fft.rfftfreq(len(x), 1 / SR)
    g = np.ones_like(f)
    if lo:
        g *= 1 / (1 + (lo / np.maximum(f, 1e-3)) ** 4)
    if hi:
        g *= 1 / (1 + (f / hi) ** 4)
    if inclinacao:
        g *= 1 / np.maximum(f, 20.0) ** inclinacao
    return np.fft.irfft(X * g, len(x))


def norm(x):
    return x / (np.std(x) + 1e-12)


def envoltoria_lenta(rng, hz, profundidade, n=N):
    """Variacao aleatoria suave de amplitude em torno de 1."""
    e = norm(filtro(rng.standard_normal(n), None, hz))
    return np.clip(1 + profundidade * e, 0.05, None)


def estereo(fn, rng):
    return np.stack([fn(rng), fn(rng)], axis=1)


def chuva(rng):
    def canal(r):
        base = 0.7 * norm(filtro(r.standard_normal(N), 400, 9000, inclinacao=0.45)) + 0.3 * norm(filtro(r.standard_normal(N), 1500, 12000))
        base *= envoltoria_lenta(r, 0.25, 0.10)
        # pingos: impulsos aleatorios filtrados em faixa aguda
        imp = np.zeros(N)
        pos = r.integers(0, N, size=SEG * 140)
        imp[pos] = r.lognormal(0.0, 0.8, size=len(pos))
        gotas = norm(filtro(imp, 1800, 7500))
        grave = norm(filtro(r.standard_normal(N), 60, 220)) * 0.25
        return base + 0.55 * gotas + grave
    return estereo(canal, rng)


def piado(rng, dur_total):
    """Frases curtas de passaros (glissandos senoidais) espalhadas de forma esparsa, com eco leve."""
    saida = np.zeros((N, 2))
    t = rng.uniform(1.5, 4.0)
    while t < dur_total - 1:
        notas = int(rng.integers(2, 6))
        f0 = rng.uniform(2600, 4600)
        pan = rng.uniform(0.15, 0.85)
        ganho = rng.uniform(0.05, 0.13)
        inicio = t
        for k in range(notas):
            d = rng.uniform(0.07, 0.16)
            n = int(d * SR)
            tt = np.arange(n) / SR
            f = f0 * (1 + rng.uniform(-0.15, 0.25) * tt / d) * (1 + 0.04 * k)
            fase = 2 * np.pi * np.cumsum(f) / SR
            env = np.sin(np.pi * tt / d) ** 2
            nota = np.sin(fase) * env + 0.25 * np.sin(2 * fase) * env
            i = int(inicio * SR)
            if i + n >= N:
                break
            saida[i:i + n, 0] += nota * ganho * (1 - pan)
            saida[i:i + n, 1] += nota * ganho * pan
            inicio += d + rng.uniform(0.05, 0.14)
        t += rng.uniform(3.5, 8.0)
    # eco curto, sugere mata aberta
    atraso = int(0.21 * SR)
    eco = np.zeros_like(saida)
    eco[atraso:] = saida[:-atraso] * 0.35
    return saida + eco


def mata(rng):
    def vento(r):
        v = norm(filtro(r.standard_normal(N), 50, 800)) * envoltoria_lenta(r, 0.18, 0.55)
        folhas = norm(filtro(r.standard_normal(N), 2500, 7000)) * envoltoria_lenta(r, 0.3, 0.7) * 0.22
        riacho = norm(filtro(r.standard_normal(N), 300, 3200)) * envoltoria_lenta(r, 6.0, 0.35) * 0.30
        return v + folhas + riacho
    base = estereo(vento, rng)
    return base + piado(rng, SEG) * 3.0


def calmo(rng):
    t = np.arange(N) / SR
    notas = [110.0, 164.81, 220.0, 277.18, 329.63]  # La maior, aberto e estavel
    pad = np.zeros((N, 2))
    for i, f in enumerate(notas):
        for lado, desvio in enumerate((-0.35, 0.35)):
            lfo = 0.55 + 0.45 * np.sin(2 * np.pi * rng.uniform(0.03, 0.08) * t + rng.uniform(0, 6.28))
            onda = np.sin(2 * np.pi * (f + desvio) * t) + 0.3 * np.sin(2 * np.pi * 2 * (f + desvio) * t)
            pad[:, lado] += onda * lfo * (1.0 / (1 + 0.35 * i))
    ar = estereo(lambda r: norm(filtro(r.standard_normal(N), 1200, 5500)) * envoltoria_lenta(r, 0.12, 0.5), rng) * 0.06
    vento = estereo(lambda r: norm(filtro(r.standard_normal(N), 60, 500)) * envoltoria_lenta(r, 0.1, 0.4), rng) * 0.10
    return pad * 0.25 + ar + vento


def finaliza(x):
    x = x - x.mean(axis=0)
    x *= 10 ** (ALVO_RMS_DB / 20) / (np.sqrt(np.mean(x ** 2)) + 1e-12)
    x = np.tanh(x * 1.2) / 1.2  # limitador suave: sem picos secos
    pico = 20 * np.log10(np.max(np.abs(x)) + 1e-12)
    if pico > -3.0:  # folga para a codificacao em AAC nao estourar
        x *= 10 ** ((-3.0 - pico) / 20)
    return x


def grava(nome, x):
    SAIDA.mkdir(parents=True, exist_ok=True)
    wav = SAIDA / f"{nome}.wav"
    with wave.open(str(wav), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((np.clip(x, -1, 1) * 32767).astype("<i2").tobytes())
    m4a = SAIDA / f"{nome}.m4a"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(wav), "-c:a", "aac", "-b:a", "96k", str(m4a)], check=True)
    wav.unlink()
    pico = 20 * np.log10(np.max(np.abs(x)) + 1e-12)
    rms = 20 * np.log10(np.sqrt(np.mean(x ** 2)) + 1e-12)
    print(f"{nome}: {m4a.stat().st_size // 1024} KB, RMS {rms:.1f} dBFS, pico {pico:.1f} dBFS")


if __name__ == "__main__":
    for nome, fn, semente in (("chuva", chuva, 11), ("mata", mata, 22), ("calmo", calmo, 33)):
        grava(nome, finaliza(fn(np.random.default_rng(semente))))
