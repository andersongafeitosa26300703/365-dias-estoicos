"""Posta no Instagram a citacao do dia.

Uso:
  python scripts/post_daily.py prepare [--day N]   # gera posts/dia-NNN.jpg e escreve a legenda
  python scripts/post_daily.py publish [--day N]   # publica pela Graph API (precisa de IG_USER_ID e IG_ACCESS_TOKEN)
  python scripts/post_daily.py preview [--day N]   # mostra legenda e dia, sem publicar nada

O dia e calculado a partir de start_date em config.json (fuso America/Sao_Paulo),
a menos que --day seja informado.
"""
import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
from render import render  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
POSTS_DIR = ROOT / "posts"
POSTED_FILE = ROOT / "data" / "posted.json"
GRAPH = "https://graph.facebook.com/v21.0"
TZ = ZoneInfo("America/Sao_Paulo")


def load_config():
    return json.loads((ROOT / "config.json").read_text(encoding="utf-8"))


def load_calendar():
    entries = json.loads((ROOT / "data" / "calendar.json").read_text(encoding="utf-8"))
    return {e["day"]: e for e in entries}


def load_posted():
    if POSTED_FILE.exists():
        return json.loads(POSTED_FILE.read_text(encoding="utf-8"))
    return {}


def today_number(cfg):
    start = datetime.strptime(cfg["start_date"], "%Y-%m-%d").date()
    return (datetime.now(TZ).date() - start).days + 1


def build_caption(entry):
    tags = " ".join(entry["hashtags"])
    parts = [
        entry["reflection"],
        f"— {entry['author']}",
        "Salve para reler quando precisar. \U0001F3DB️",
        tags,
    ]
    return "\n\n".join(parts)


def image_url(day):
    repo = os.environ["GITHUB_REPOSITORY"]
    branch = os.environ.get("GITHUB_REF_NAME", "main")
    return f"https://raw.githubusercontent.com/{repo}/{branch}/posts/dia-{day:03d}.jpg"


def graph_post(path, **params):
    r = requests.post(f"{GRAPH}/{path}", data=params, timeout=60)
    body = r.json()
    if r.status_code >= 400:
        raise RuntimeError(f"Graph API {path}: {body}")
    return body


def graph_get(path, **params):
    r = requests.get(f"{GRAPH}/{path}", params=params, timeout=60)
    body = r.json()
    if r.status_code >= 400:
        raise RuntimeError(f"Graph API {path}: {body}")
    return body


def resolve_day(args, cfg):
    day = args.day or today_number(cfg)
    if day < 1 or day > 365:
        print(f"Dia {day} fora do intervalo 1..365; nada a postar.")
        sys.exit(0)
    return day


def cmd_prepare(day, entry):
    out = render(entry, POSTS_DIR / f"dia-{day:03d}.jpg")
    (POSTS_DIR / f"dia-{day:03d}.txt").write_text(build_caption(entry), encoding="utf-8")
    print(f"Dia {day}: imagem em {out}")


def cmd_publish(day, entry):
    posted = load_posted()
    if str(day) in posted:
        print(f"Dia {day} ja foi publicado ({posted[str(day)]}); nada a fazer.")
        return

    user_id = os.environ["IG_USER_ID"]
    token = os.environ["IG_ACCESS_TOKEN"]
    caption = (POSTS_DIR / f"dia-{day:03d}.txt").read_text(encoding="utf-8")
    url = image_url(day)

    # raw.githubusercontent pode demorar alguns segundos para servir o arquivo recem-enviado
    for _ in range(12):
        if requests.head(url, timeout=30).status_code == 200:
            break
        time.sleep(10)
    else:
        raise RuntimeError(f"Imagem nao acessivel publicamente: {url}")

    container = graph_post(f"{user_id}/media", image_url=url, caption=caption, access_token=token)["id"]

    for _ in range(30):
        status = graph_get(container, fields="status_code", access_token=token)["status_code"]
        if status == "FINISHED":
            break
        if status in ("ERROR", "EXPIRED"):
            raise RuntimeError(f"Container {container} com status {status}")
        time.sleep(5)
    else:
        raise RuntimeError(f"Container {container} nao ficou pronto a tempo")

    media_id = graph_post(f"{user_id}/media_publish", creation_id=container, access_token=token)["id"]
    posted[str(day)] = {"media_id": media_id, "at": datetime.now(TZ).isoformat(timespec="seconds")}
    POSTED_FILE.write_text(json.dumps(posted, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Dia {day} publicado: media_id={media_id}")


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("command", choices=["prepare", "publish", "preview"])
    ap.add_argument("--day", type=int)
    args = ap.parse_args()

    cfg = load_config()
    day = resolve_day(args, cfg)
    entry = load_calendar().get(day)
    if entry is None:
        raise SystemExit(f"Dia {day} nao existe em data/calendar.json")

    if args.command == "preview":
        print(f"--- Dia {day} ({entry['theme']}) ---\n{build_caption(entry)}")
    elif args.command == "prepare":
        cmd_prepare(day, entry)
    else:
        cmd_publish(day, entry)


if __name__ == "__main__":
    main()
