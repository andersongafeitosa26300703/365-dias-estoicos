"""Confere se o post (feed e Story) de hoje foi publicado. Sai com erro (exit 1) se faltar algo,
o que faz o workflow falhar e o GitHub avisar o dono por e-mail.

Uso: python scripts/check_today.py [--day N]
"""
import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
TZ = ZoneInfo("America/Sao_Paulo")


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--day", type=int)
    args = ap.parse_args()

    cfg = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
    start = datetime.strptime(cfg["start_date"], "%Y-%m-%d").date()
    day = args.day or (datetime.now(TZ).date() - start).days + 1
    if day < 1 or day > 365:
        print(f"Dia {day} fora do intervalo 1..365; nada a conferir.")
        return

    posted_file = ROOT / "data" / "posted.json"
    posted = json.loads(posted_file.read_text(encoding="utf-8")) if posted_file.exists() else {}
    rec = posted.get(str(day), {})
    missing = [name for name, key in (("feed", "media_id"), ("Story", "story_media_id")) if not rec.get(key)]
    if missing:
        print(f"PROBLEMA: o dia {day} NAO foi publicado completo. Faltando: {', '.join(missing)}.")
        print("Proximo passo: abra Actions > 'Post diario 365 Dias Estoicos' > Run workflow (deixe o dia vazio), "
              "ou peca ao Claude para disparar. Se o motivo for o token, rode scripts/get_token.py e atualize IG_ACCESS_TOKEN.")
        sys.exit(1)
    print(f"OK: dia {day} publicado no feed e no Story em {rec.get('at')}.")


if __name__ == "__main__":
    main()
