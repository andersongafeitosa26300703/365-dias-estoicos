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
from render import render, render_story  # noqa: E402

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


def image_url(name):
    repo = os.environ["GITHUB_REPOSITORY"]
    branch = os.environ.get("GITHUB_REF_NAME", "main")
    return f"https://raw.githubusercontent.com/{repo}/{branch}/posts/{name}"


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


def resolve_ig(user_id, token):
    """Aceita token de Pagina ou de usuario: se o ID cadastrado nao funcionar, descobre Pagina e Instagram pelo token."""
    if user_id.isdigit():
        r = requests.get(f"{GRAPH}/{user_id}", params={"fields": "id", "access_token": token}, timeout=60)
        if r.status_code == 200:
            return user_id, token
    r = requests.get(
        f"{GRAPH}/me/accounts",
        params={"fields": "name,access_token,instagram_business_account", "access_token": token},
        timeout=60,
    )
    pages = [p for p in r.json().get("data", []) if p.get("instagram_business_account")] if r.status_code < 400 else []
    if not pages:
        # Token de Pagina: o proprio /me e a Pagina
        me = requests.get(
            f"{GRAPH}/me",
            params={"fields": "id,name,instagram_business_account", "access_token": token},
            timeout=60,
        )
        mb = me.json()
        if me.status_code < 400 and mb.get("instagram_business_account"):
            print(f"[resolve] token de Pagina '{mb.get('name')}'")
            return mb["instagram_business_account"]["id"], token
        raise RuntimeError("Nenhuma Pagina com Instagram vinculado foi encontrada para este token")
    pages.sort(key=lambda p: "Estoic" not in p["name"])
    page = pages[0]
    print(f"[resolve] Instagram encontrado pela Pagina '{page['name']}'")
    return page["instagram_business_account"]["id"], page["access_token"]


def clean_secret(value):
    """Remove bytes nulos, espacos e quebras de linha que a colagem pode ter trazido."""
    return "".join(ch for ch in value if ch.isprintable() and not ch.isspace())


def diagnose(user_id, token):
    """Imprime pistas sobre a falha sem expor segredos (o log de repositorio publico e publico)."""
    print(f"[diag] IG_USER_ID: {len(user_id)} caracteres, so digitos: {user_id.isdigit()}")
    print(f"[diag] IG_ACCESS_TOKEN: {len(token)} caracteres, comeca com EAA: {token.startswith('EAA')}")
    r = requests.get(f"{GRAPH}/{user_id}", params={"fields": "id,username", "access_token": token}, timeout=60)
    print(f"[diag] ler a conta do IG: HTTP {r.status_code}", r.json().get("error", {}).get("message", "ok"))
    r = requests.get(f"{GRAPH}/me", params={"fields": "id,name", "access_token": token}, timeout=60)
    b = r.json()
    print(f"[diag] /me: HTTP {r.status_code}", b.get("error", {}).get("message", ""))
    if r.status_code == 200:
        print(f"[diag] /me id == IG_USER_ID: {b.get('id') == user_id}; nome contem 'Estoic': {'Estoic' in b.get('name', '')}")
    r = requests.get(f"{GRAPH}/me/permissions", params={"access_token": token}, timeout=60)
    if r.status_code == 200:
        print("[diag] permissoes:", sorted(p["permission"] for p in r.json().get("data", []) if p["status"] == "granted"))


def resolve_day(args, cfg):
    day = args.day or today_number(cfg)
    if day < 1 or day > 365:
        print(f"Dia {day} fora do intervalo 1..365; nada a postar.")
        sys.exit(0)
    return day


def cmd_prepare(day, entry):
    out = render(entry, POSTS_DIR / f"dia-{day:03d}.jpg")
    render_story(entry, POSTS_DIR / f"story-{day:03d}.jpg")
    (POSTS_DIR / f"dia-{day:03d}.txt").write_text(build_caption(entry), encoding="utf-8")
    print(f"Dia {day}: imagem em {out} (e versao Story)")


def wait_public(url):
    # raw.githubusercontent pode demorar alguns segundos para servir o arquivo recem-enviado
    for _ in range(12):
        if requests.head(url, timeout=30).status_code == 200:
            return
        time.sleep(10)
    raise RuntimeError(f"Imagem nao acessivel publicamente: {url}")


def create_and_publish(user_id, token, **params):
    """Cria o container de midia, espera ficar pronto e publica. Serve para feed e Stories."""
    container = graph_post(f"{user_id}/media", access_token=token, **params)["id"]
    for _ in range(30):
        status = graph_get(container, fields="status_code", access_token=token)["status_code"]
        if status == "FINISHED":
            break
        if status in ("ERROR", "EXPIRED"):
            raise RuntimeError(f"Container {container} com status {status}")
        time.sleep(5)
    else:
        raise RuntimeError(f"Container {container} nao ficou pronto a tempo")
    # O Instagram as vezes marca o container como FINISHED mas ainda recusa publicar (erro 9007/2207027): tenta de novo
    last = None
    for _ in range(8):
        try:
            return graph_post(f"{user_id}/media_publish", creation_id=container, access_token=token)["id"]
        except RuntimeError as e:
            last = e
            if "9007" in str(e) or "2207027" in str(e) or "not available" in str(e):
                time.sleep(10)
                continue
            raise
    raise last


def save_posted(posted):
    POSTED_FILE.write_text(json.dumps(posted, indent=2, ensure_ascii=False), encoding="utf-8")


def cmd_publish(day, entry):
    posted = load_posted()
    rec = posted.get(str(day), {})
    feed_done, story_done = bool(rec.get("media_id")), bool(rec.get("story_media_id"))
    if feed_done and story_done:
        print(f"Dia {day} ja foi publicado (feed e Story); nada a fazer.")
        return

    user_id = clean_secret(os.environ["IG_USER_ID"])
    token = clean_secret(os.environ["IG_ACCESS_TOKEN"])
    user_id, token = resolve_ig(user_id, token)

    if not feed_done:
        caption = (POSTS_DIR / f"dia-{day:03d}.txt").read_text(encoding="utf-8")
        url = image_url(f"dia-{day:03d}.jpg")
        wait_public(url)
        try:
            media_id = create_and_publish(user_id, token, image_url=url, caption=caption)
        except RuntimeError:
            diagnose(user_id, token)
            raise
        rec = {"media_id": media_id, "at": datetime.now(TZ).isoformat(timespec="seconds")}
        posted[str(day)] = rec
        save_posted(posted)  # grava ja: o feed nunca pode ser publicado duas vezes
        print(f"Dia {day} publicado no feed: media_id={media_id}")

    if not story_done:
        try:
            surl = image_url(f"story-{day:03d}.jpg")
            wait_public(surl)
            story_id = create_and_publish(user_id, token, image_url=surl, media_type="STORIES")
            rec["story_media_id"] = story_id
            posted[str(day)] = rec
            save_posted(posted)
            print(f"Dia {day} publicado no Story: media_id={story_id}")
        except RuntimeError as e:
            # O feed ja saiu; falha no Story so avisa (exit 1 no fim, depois de registrar o feed)
            print(f"[story] FALHOU (o feed do dia {day} ja foi publicado): {e}")
            sys.exit(1)


def cmd_token_info():
    """Mostra a validade do token (sem expor o token). Sai com erro se faltarem menos de 14 dias."""
    token = clean_secret(os.environ["IG_ACCESS_TOKEN"])
    r = requests.get(f"{GRAPH}/debug_token", params={"input_token": token, "access_token": token}, timeout=60)
    body = r.json()
    if r.status_code >= 400 or "data" not in body:
        print(f"[token] nao foi possivel inspecionar o token: {body.get('error', {}).get('message', body)}")
        sys.exit(1)
    d = body["data"]
    now = datetime.now(TZ)

    def when(ts):
        if not ts:
            return None
        dt = datetime.fromtimestamp(ts, TZ)
        return dt, (dt - now).days

    exp, data_exp = when(d.get("expires_at")), when(d.get("data_access_expires_at"))
    print(f"[token] tipo: {d.get('type')}; valido: {d.get('is_valid')}")
    print("[token] expira em:", f"{exp[0]:%d/%m/%Y} (faltam {exp[1]} dias)" if exp else "nunca expira")
    print("[token] acesso a dados expira em:", f"{data_exp[0]:%d/%m/%Y} (faltam {data_exp[1]} dias)" if data_exp else "sem data")
    print("[token] permissoes:", ", ".join(d.get("scopes", [])))
    # Testa tambem a descoberta da conta do Instagram (sem postar nada)
    try:
        ig_id, _ = resolve_ig(clean_secret(os.environ.get("IG_USER_ID", "")), token)
        print(f"[token] conta do Instagram encontrada (ID com {len(ig_id)} digitos, so numeros: {ig_id.isdigit()})")
    except RuntimeError as e:
        print(f"[token] FALHA ao descobrir a conta do Instagram: {e}")
        sys.exit(1)
    left = [x[1] for x in (exp, data_exp) if x]
    if not d.get("is_valid") or (left and min(left) < 14):
        print("[token] ATENCAO: renove o token (rode scripts/get_token.py e atualize os segredos no GitHub)")
        sys.exit(1)


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("command", choices=["prepare", "publish", "preview", "token-info"])
    ap.add_argument("--day", type=int)
    args = ap.parse_args()

    if args.command == "token-info":
        cmd_token_info()
        return

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
