"""Le as metricas das publicacoes registradas em data/posted.json (somente leitura).

Uso: python scripts/metricas.py [--saida metricas.json]
Precisa de IG_USER_ID e IG_ACCESS_TOKEN. Curtidas, comentarios e seguidores sao dados publicos e vao para o log.
Alcance, visualizacoes, salvamentos e compartilhamentos (insights, exigem instagram_manage_insights) vao so
para o arquivo de saida, porque o log de um repositorio publico e publico.
"""
import argparse
import json
import os
import sys
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
from post_daily import GRAPH, POSTED_FILE, clean_secret, resolve_ig  # noqa: E402

INSIGHTS_FEED = "reach,saved,shares,total_interactions,views"
INSIGHTS_REEL = "reach,saved,shares,total_interactions,views,ig_reels_avg_watch_time"


def get(url, **params):
    r = requests.get(url, params=params, timeout=60)
    try:
        body = r.json()
    except ValueError:
        body = {}
    return r.status_code, body


def insights(media_id, token, metrics):
    status, body = get(f"{GRAPH}/{media_id}/insights", metric=metrics, access_token=token)
    if status >= 400:
        return None, body.get("error", {}).get("message", f"HTTP {status}")
    return {m["name"]: (m.get("values") or [{}])[0].get("value") for m in body.get("data", [])}, None


def media(media_id, token, kind):
    status, body = get(
        f"{GRAPH}/{media_id}",
        fields="like_count,comments_count,media_type,timestamp",
        access_token=token,
    )
    if status >= 400:
        return {"erro": body.get("error", {}).get("message", f"HTTP {status}")}
    ins, err = insights(media_id, token, INSIGHTS_REEL if kind == "reel" else INSIGHTS_FEED)
    out = {k: body.get(k) for k in ("like_count", "comments_count", "media_type", "timestamp")}
    out["insights"] = ins
    out["insights_erro"] = err
    return out


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--saida", default="metricas.json")
    args = ap.parse_args()

    user_id, token = resolve_ig(clean_secret(os.environ["IG_USER_ID"]), clean_secret(os.environ["IG_ACCESS_TOKEN"]))
    posted = json.loads(POSTED_FILE.read_text(encoding="utf-8"))

    status, conta = get(f"{GRAPH}/{user_id}", fields="followers_count,media_count", access_token=token)
    print("Conta:", conta if status < 400 else conta.get("error", {}).get("message"))

    resultado = {"conta": conta, "dias": {}}
    print("dia | formato | feed curtidas/coment | reel curtidas/coment | reel anterior curtidas/coment")
    for dia in sorted(posted, key=int):
        rec = posted[dia]
        item = {"formato": rec.get("formato", "imagem")}
        if rec.get("media_id"):
            item["feed"] = media(rec["media_id"], token, "feed")
        if rec.get("reel_media_id"):
            item["reel"] = media(rec["reel_media_id"], token, "reel")
        if rec.get("reel_anterior_media_id"):
            item["reel_anterior"] = media(rec["reel_anterior_media_id"], token, "reel")
        resultado["dias"][dia] = item

        def lc(parte):
            m = item.get(parte)
            return "-" if not m or "erro" in m else f"{m.get('like_count')}/{m.get('comments_count')}"

        print(f"{int(dia):>3} | {item['formato']:<9} | {lc('feed'):>8} | {lc('reel'):>8} | {lc('reel_anterior'):>8}")

    Path(args.saida).write_text(json.dumps(resultado, ensure_ascii=False, indent=1), encoding="utf-8")
    erros = {
        parte.get("insights_erro")
        for d in resultado["dias"].values()
        for parte in d.values()
        if isinstance(parte, dict) and parte.get("insights_erro")
    }
    if erros:
        print("Insights indisponiveis (provavel falta da permissao instagram_manage_insights):", list(erros)[:1])


if __name__ == "__main__":
    main()
