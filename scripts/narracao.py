"""Gera o video narrado do dia seguinte: a voz do autor (ElevenLabs) le a citacao, o autor e o "No trabalho".

Fluxo: texto -> voz (API da ElevenLabs) -> instantes de cada parte medidos nas pausas da fala -> video estatico em
reels/dia-NNN.mp4 (+ dia-NNN.json com "narrado": true). No dia seguinte o `prepare` mantem esse video e o `publish-reel`
o publica. Sem o arquivo, a rotina publica o Reel de sempre.

Precisa de ELEVENLABS_API_KEY (segredo do GitHub, nunca no codigo), ffmpeg e do plano da ElevenLabs que permita a API.
Desligado por padrao: "narracao": true em config.json.

Uso:
  python scripts/narracao.py                       # gera o video de amanha (America/Sao_Paulo)
  python scripts/narracao.py --dia 44              # um dia especifico
  python scripts/narracao.py --dia 44 --audio x.mp3   # usa uma voz ja gravada (nao chama a API)
  python scripts/narracao.py --forcar              # ignora "narracao": false e refaz se ja existir
"""
import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
from narrado import estatico  # noqa: E402
from reel import ROOT  # noqa: E402
from reel_carrossel import CAPA_MS, reel_carrossel, texto_carrossel  # noqa: E402
from reel_carrossel import usa_formato as reel_carrossel_usa  # noqa: E402

TZ = ZoneInfo("America/Sao_Paulo")
REELS_DIR = ROOT / "reels"
ATRASO = 0.4  # silencio antes da fala, em segundos


def numero_de_amanha(cfg):
    inicio = datetime.strptime(cfg["start_date"], "%Y-%m-%d").date()
    return (datetime.now(TZ).date() - inicio).days + 2


def texto_narracao(entry):
    """Texto enviado a voz. As marcacoes entre colchetes dao o ritmo (lento, misterioso) e as pausas; nao sao lidas."""
    partes = [f"[slowly] [mysterious] “{entry['quote']}”", "[long pause]", f"{entry['author']}.", "[long pause]"]
    if entry.get("apply"):
        partes.append(f"[slowly] No trabalho… {entry['apply']}")
    return " ".join(partes)


def texto_do_dia(entry, cfg=None):
    """Texto da voz do dia: o do carrossel narrado (config narracao_formato = "carrossel", dia com gancho) ou o curto."""
    cfg = cfg if cfg is not None else json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
    if cfg.get("narracao_formato") == "carrossel" and reel_carrossel_usa(entry):
        return texto_carrossel(entry)
    return texto_narracao(entry)


def voz_do_autor(autor):
    cfg = json.loads((ROOT / "data" / "vozes.json").read_text(encoding="utf-8"))
    escolha = cfg["autores"].get(autor) or cfg["padrao"]
    return escolha["voz"], cfg["modelo"], escolha["nome"]


def gerar_voz(texto, voz_id, modelo, saida):
    chave = os.environ.get("ELEVENLABS_API_KEY", "").strip()
    if not chave:
        raise SystemExit("Falta o segredo ELEVENLABS_API_KEY (GitHub: Settings > Secrets and variables > Actions).")
    r = requests.post(
        f"https://api.elevenlabs.io/v1/text-to-speech/{voz_id}",
        params={"output_format": "mp3_44100_128"},
        headers={"xi-api-key": chave, "Content-Type": "application/json"},
        json={"text": texto, "model_id": modelo},
        timeout=180,
    )
    if r.status_code != 200:
        raise RuntimeError(f"ElevenLabs respondeu HTTP {r.status_code}: {r.text[:300]}")
    Path(saida).write_bytes(r.content)


def _duracao(arquivo):
    return float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(arquivo)],
                                capture_output=True, text=True, check=True).stdout)


def tempos_da_fala(audio, entry):
    """Instantes (s, ja somado o ATRASO) em que o texto entra: citacao, autor e 'No trabalho'.
    As duas maiores pausas da fala separam as partes; sem elas, divide pelo tamanho do texto."""
    dur = _duracao(audio)
    saida = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(audio), "-af", "silencedetect=noise=-38dB:d=0.6", "-f", "null", "-"],
                           capture_output=True, text=True).stderr
    inicios = [float(x) for x in re.findall(r"silence_start: ([\d.]+)", saida)]
    fins = [(float(e), float(d)) for e, d in re.findall(r"silence_end: ([\d.]+) \| silence_duration: ([\d.]+)", saida)]
    pausas = [(ini, fim, dur_p) for ini, (fim, dur_p) in zip(inicios, fins)]
    quantas = 2 if entry.get("apply") else 1
    maiores = sorted(sorted(pausas, key=lambda p: -p[2])[:quantas], key=lambda p: p[0])
    t = {"quote": ATRASO + 0.1}
    if len(maiores) == quantas and all(p[0] > 2.0 for p in maiores):
        t["label"] = ATRASO + maiores[0][1] - 0.1
        if quantas == 2:
            t["apply"] = ATRASO + maiores[1][1] - 0.1
        if quantas == 1 or t["apply"] > t["label"] + 0.8:
            return t
    # Plano B: proporcional ao tamanho de cada parte
    q, a = len(entry["quote"]), len(entry.get("apply") or "")
    total = q + len(entry["author"]) + a
    t["label"] = ATRASO + dur * q / total
    if a:
        t["apply"] = ATRASO + dur * (q + len(entry["author"])) / total
    print("[tempos] pausas nao identificadas; usando divisao proporcional")
    return t


def gerar(dia, audio=None, forcar=False):
    cfg = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
    if not cfg.get("narracao") and not forcar:
        print('Narracao desligada (config.json: "narracao" = false); nada a fazer.')
        return None
    if not 1 <= dia <= 365:
        print(f"Dia {dia} fora do intervalo 1..365; nada a gerar.")
        return None
    entry = next(e for e in json.loads((ROOT / "data" / "calendar.json").read_text(encoding="utf-8")) if e["day"] == dia)
    destino = REELS_DIR / f"dia-{dia:03d}.mp4"
    meta = REELS_DIR / f"dia-{dia:03d}.json"
    if meta.exists() and json.loads(meta.read_text(encoding="utf-8")).get("narrado") and not forcar:
        print(f"Dia {dia}: video narrado ja existe; nada a fazer.")
        return destino
    voz_id, modelo, nome_voz = voz_do_autor(entry["author"])
    # Formato "carrossel": o Reel le as 5 laminas do carrossel (so em dias com gancho); senao, o narrado curto
    longo = cfg.get("narracao_formato") == "carrossel" and reel_carrossel_usa(entry)
    if audio is None:
        audio = Path(os.environ.get("RUNNER_TEMP", "/tmp")) / f"narracao-{dia:03d}.mp3"
        gerar_voz(texto_do_dia(entry, cfg), voz_id, modelo, audio)
    if longo:
        mp4, total = reel_carrossel(entry, audio, destino)
        meta.write_text(json.dumps({"duracao_s": round(total, 1), "capa_ms": CAPA_MS, "narrado": True, "voz": nome_voz,
                                    "formato": "carrossel narrado"}, ensure_ascii=False), encoding="utf-8")
    else:
        tempos = tempos_da_fala(audio, entry)
        mp4, total = estatico(entry, audio, destino, tempos, atraso=ATRASO)
        meta.write_text(json.dumps({"duracao_s": round(total, 1), "capa_ms": int(max(0, total - 1.0) * 1000), "narrado": True,
                                    "voz": nome_voz}), encoding="utf-8")
    print(f"Dia {dia}: video narrado de {total:.0f} s com a voz de {nome_voz} em {mp4}")
    return mp4


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--dia", type=int)
    ap.add_argument("--audio")
    ap.add_argument("--forcar", action="store_true")
    a = ap.parse_args()
    cfg = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
    gerar(a.dia or numero_de_amanha(cfg), a.audio, a.forcar)
