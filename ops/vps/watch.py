#!/usr/bin/env python3
"""Vigia do 365 Dias Estoicos e do ResumoIA, para rodar numa VPS (fora do agendador do GitHub).

O que faz a cada execucao:
  1. Calcula o numero do dia de hoje (fuso de Brasilia) a partir do config.json do repositorio.
  2. Le data/posted.json (publico) e confere se o feed e o Story de hoje foram publicados.
  3. Tudo certo  -> nao avisa (ou avisa "ok" se NOTIFY_OK=1, uma vez por dia).
     Faltando    -> se houver GH_TOKEN e ainda nao tentou hoje, DISPARA o workflow pela API do GitHub;
                    nas execucoes seguintes, se continuar faltando, AVISA no celular (ntfy.sh).

So usa a biblioteca padrao do Python 3.9+. Configuracao por variaveis de ambiente (arquivo /etc/365dias.env).
"""
import json
import os
import re
import sys
import tempfile
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ENV_FILE = os.environ.get("ENV_FILE", "/etc/365dias.env")


def load_env_file(path):
    p = Path(path)
    if not p.exists():
        return
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


load_env_file(ENV_FILE)

REPO = os.environ.get("REPO", "andersongafeitosa26300703/365-dias-estoicos")
BRANCH = os.environ.get("BRANCH", "main")
WORKFLOW = os.environ.get("WORKFLOW", "daily-post.yml")
NTFY_TOPIC = os.environ.get("NTFY_TOPIC", "")
NTFY_SERVER = os.environ.get("NTFY_SERVER", "https://ntfy.sh")
GH_TOKEN = os.environ.get("GH_TOKEN", "")
DRY_RUN = os.environ.get("DRY_RUN", "0") == "1"
NOTIFY_OK = os.environ.get("NOTIFY_OK", "0") == "1"
STATE_DIR = Path(os.environ.get("STATE_DIR", tempfile.gettempdir()))
TZ = ZoneInfo("America/Sao_Paulo")
RESUMO_REPO = os.environ.get("RESUMO_REPO", "andersongafeitosa26300703/resumoia")
RESUMO_WORKFLOW = os.environ.get("RESUMO_WORKFLOW", "scheduled.yml")
RESUMO_GH_TOKEN = os.environ.get("RESUMO_GH_TOKEN", "")  # opcional: PAT com Actions (write) no repo do ResumoIA


def http(url, data=None, headers=None, method=None, timeout=30):
    req = urllib.request.Request(url, data=data, headers=headers or {}, method=method)
    req.add_header("User-Agent", "365dias-watch/1.0")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.status, r.read()


def notify(title, message, priority="high", tags="warning"):
    print(f"[aviso] {title}: {message}")
    if DRY_RUN:
        return
    if not NTFY_TOPIC:
        print("[aviso] NTFY_TOPIC nao configurado; nao foi possivel enviar ao celular.", file=sys.stderr)
        return
    try:
        # Cabecalhos HTTP so aceitam latin-1; o titulo vai sem acentos problematicos
        http(
            f"{NTFY_SERVER}/{NTFY_TOPIC}",
            data=message.encode("utf-8"),
            headers={"Title": title.encode("latin-1", "ignore").decode("latin-1"), "Priority": priority, "Tags": tags},
            method="POST",
        )
    except Exception as e:  # noqa: BLE001
        print(f"[erro] falha ao enviar aviso: {e}", file=sys.stderr)


def today_number():
    status, body = http(f"https://raw.githubusercontent.com/{REPO}/{BRANCH}/config.json")
    start = datetime.strptime(json.loads(body)["start_date"], "%Y-%m-%d").date()
    return (datetime.now(TZ).date() - start).days + 1


def read_posted():
    # API de conteudo (sem cache longo); aceita leitura anonima de repositorio publico
    status, body = http(
        f"https://api.github.com/repos/{REPO}/contents/data/posted.json?ref={BRANCH}",
        headers={"Accept": "application/vnd.github.raw"},
    )
    return json.loads(body)


def dispatch():
    if DRY_RUN:
        print("[dry-run] dispararia o workflow agora")
        return True
    status, _ = http(
        f"https://api.github.com/repos/{REPO}/actions/workflows/{WORKFLOW}/dispatches",
        data=json.dumps({"ref": BRANCH}).encode(),
        headers={
            "Authorization": f"Bearer {GH_TOKEN}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    return status == 204


def check_365():
    day = int(os.environ["DAY"]) if os.environ.get("DAY") else today_number()
    if not 1 <= day <= 365:
        print(f"Dia {day} fora do intervalo 1..365; nada a conferir.")
        return
    today = datetime.now(TZ).strftime("%Y-%m-%d")
    rec = read_posted().get(str(day), {})
    missing = [n for n, k in (("feed", "media_id"), ("Story", "story_media_id")) if not rec.get(k)]

    if not missing:
        print(f"OK: dia {day} publicado no feed e no Story ({rec.get('at')}).")
        flag = STATE_DIR / f"365dias-ok-{today}"
        if NOTIFY_OK and not flag.exists():
            notify(f"Dia {day} publicado", "Feed e Story no ar.", priority="low", tags="white_check_mark")
            if not DRY_RUN:
                flag.write_text("ok")
        return

    what = " e ".join(missing)
    triggered = STATE_DIR / f"365dias-triggered-{today}"
    if GH_TOKEN and not triggered.exists():
        ok = False
        try:
            ok = dispatch()
        except urllib.error.HTTPError as e:
            print(f"[erro] disparo recusado pelo GitHub: HTTP {e.code}", file=sys.stderr)
        except Exception as e:  # noqa: BLE001
            print(f"[erro] disparo falhou: {e}", file=sys.stderr)
        if not DRY_RUN:
            triggered.write_text("1")
        if ok:
            notify(
                f"Dia {day}: disparei o post",
                f"O agendamento do GitHub nao publicou ({what}). Disparei o workflow agora; vou conferir de novo.",
                priority="default",
                tags="rocket",
            )
            return
    tried = "e a nova tentativa nao resolveu" if GH_TOKEN else "(o vigia nao tem token para tentar disparar)"
    notify(
        f"POSTAGEM FALHOU - dia {day}",
        f"Faltando: {what}. O GitHub nao publicou {tried}. "
        f"Abra o Claude e peca para disparar o workflow, ou rode Actions > Post diario > Run workflow.",
        priority="urgent",
        tags="rotating_light",
    )


def check_resumoia():
    """Post aprovado do ResumoIA (Issue aberta com rotulo 'aprovado' e data <= hoje) que ainda nao saiu."""
    now = datetime.now(TZ)
    today = os.environ.get("TODAY") or now.strftime("%Y-%m-%d")
    # So cobra depois que o publicador (5h e reserva 5h30) teve chance de rodar
    if (now.hour, now.minute) < (5, 40) and not os.environ.get("FORCE_LATE"):
        print("ResumoIA: cedo demais para cobrar (a publicacao e as 5h/5h30); ate as 5h40 nao confiro.")
        return
    status, body = http(
        f"https://api.github.com/repos/{RESUMO_REPO}/issues?state=open&labels=aprovado&per_page=20",
        headers={"Accept": "application/vnd.github+json"},
    )
    due = []
    for it in json.loads(body):
        if "pull_request" in it:
            continue
        m = re.search(r"(\d{4}-\d{2}-\d{2})\s*$", it.get("title", ""))
        if m and m.group(1) <= today:
            due.append((m.group(1), it["number"]))
    if not due:
        print(f"ResumoIA: nada aprovado pendente para {today}.")
        return
    date, num = sorted(due)[0]
    print(f"ResumoIA: aprovado para {date} (Issue #{num}) e ainda nao publicado.")
    triggered = STATE_DIR / f"resumoia-triggered-{today}"
    if RESUMO_GH_TOKEN and not triggered.exists():
        ok = False
        try:
            if DRY_RUN:
                print("[dry-run] dispararia o workflow do ResumoIA agora")
                ok = True
            else:
                st, _ = http(
                    f"https://api.github.com/repos/{RESUMO_REPO}/actions/workflows/{RESUMO_WORKFLOW}/dispatches",
                    data=json.dumps({"ref": "main"}).encode(),
                    headers={
                        "Authorization": f"Bearer {RESUMO_GH_TOKEN}",
                        "Accept": "application/vnd.github+json",
                        "X-GitHub-Api-Version": "2022-11-28",
                        "Content-Type": "application/json",
                    },
                    method="POST",
                )
                ok = st == 204
        except Exception as e:  # noqa: BLE001
            print(f"[erro] disparo do ResumoIA falhou: {e}", file=sys.stderr)
        if not DRY_RUN:
            triggered.write_text("1")
        if ok:
            notify(
                "ResumoIA: disparei a publicacao",
                f"O post aprovado de {date} nao saiu no horario. Disparei o publicador; vou conferir de novo.",
                priority="default",
                tags="rocket",
            )
            return
    notify(
        "POSTAGEM FALHOU - ResumoIA",
        f"O post aprovado de {date} (Issue #{num}) nao foi publicado. "
        f"Abra o Claude e peca para publicar, ou rode Actions > 5 - Publicar aprovados do dia > Run workflow.",
        priority="urgent",
        tags="rotating_light",
    )


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    for name, fn in (("365 Dias Estoicos", check_365), ("ResumoIA", check_resumoia)):
        try:
            fn()
        except Exception as e:  # noqa: BLE001  - um projeto com problema nao pode calar o outro
            print(f"[erro] conferencia do {name} falhou: {e}", file=sys.stderr)


if __name__ == "__main__":
    main()
