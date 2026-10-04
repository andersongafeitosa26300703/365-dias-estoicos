"""Troca o token curto do Graph API Explorer pelo token de Pagina (que nao expira)
e mostra o ID da conta do Instagram.

Rode no seu terminal (os valores sao pedidos sem eco e nao ficam salvos em arquivo):
  python scripts/get_token.py

O token da Pagina e copiado para a area de transferencia (Windows) para voce colar
direto no GitHub (Settings > Secrets > IG_ACCESS_TOKEN). Nao cole token em chats.
"""
import getpass
import subprocess
import sys

import requests

GRAPH = "https://graph.facebook.com/v21.0"


def get(path, **params):
    r = requests.get(f"{GRAPH}/{path}", params=params, timeout=60)
    body = r.json()
    if r.status_code >= 400:
        sys.exit(f"Erro da API em {path}: {body.get('error', body)}")
    return body


def main():
    app_id = input("ID do app (App ID) [4543833645854405]: ").strip() or "4543833645854405"
    short = getpass.getpass("1) Cole o token do Explorer (nao aparece na tela) e aperte Enter: ").strip()
    app_secret = getpass.getpass("2) Agora copie a chave secreta do app, cole aqui e aperte Enter: ").strip()

    long_user = get(
        "oauth/access_token",
        grant_type="fb_exchange_token",
        client_id=app_id,
        client_secret=app_secret,
        fb_exchange_token=short,
    )["access_token"]

    pages = get(
        "me/accounts",
        fields="name,access_token,instagram_business_account{id,username}",
        access_token=long_user,
    ).get("data", [])

    if not pages:
        sys.exit("Nenhuma Pagina encontrada. Confirme que voce marcou a Pagina ao autorizar o token.")

    print("\nPaginas encontradas:")
    for i, p in enumerate(pages, 1):
        ig = p.get("instagram_business_account")
        ig_txt = f"Instagram @{ig['username']} (ID {ig['id']})" if ig else "SEM Instagram vinculado"
        print(f"  {i}. {p['name']}  ->  {ig_txt}")

    idx = int(input("\nQual Pagina e a do 365 Dias Estoicos? (numero): ")) - 1
    page = pages[idx]
    ig = page.get("instagram_business_account")
    if not ig:
        sys.exit("Essa Pagina nao tem Instagram profissional vinculado. Vincule no app do Instagram e rode de novo.")

    print(f"\nIG_USER_ID = {ig['id']}   (@{ig['username']})")
    try:
        subprocess.run("clip", input=page["access_token"].encode("utf-16le"), check=True)
        print("IG_ACCESS_TOKEN copiado para a area de transferencia. Cole no GitHub agora.")
    except Exception:
        print("Nao consegui copiar automaticamente. Token da Pagina:\n" + page["access_token"])


if __name__ == "__main__":
    main()
