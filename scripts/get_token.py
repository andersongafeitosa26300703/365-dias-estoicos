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

    # Autoverificacao: o token da Pagina precisa conseguir ler a conta do Instagram
    check = requests.get(
        f"{GRAPH}/{ig['id']}",
        params={"fields": "username", "access_token": page["access_token"]},
        timeout=60,
    )
    if check.status_code >= 400:
        sys.exit(f"Verificacao FALHOU: o token nao acessa a conta do Instagram: {check.json().get('error', check.text)}")
    print(f"\nVerificacao OK: o token acessa @{check.json().get('username')}")

    def copiar(texto):
        subprocess.run("clip", input=texto.encode("utf-16le"), check=True)

    print("\n=== PASSO A: IG_USER_ID ===")
    print(f"O numero e {ig['id']}  (conta @{ig['username']}). Ele ja foi copiado para a area de transferencia.")
    print("No GitHub: abra o segredo IG_USER_ID (lapis), cole com Ctrl+V e salve.")
    copiar(ig["id"])
    input("Quando tiver salvo o IG_USER_ID, volte aqui e aperte Enter... ")

    print("\n=== PASSO B: IG_ACCESS_TOKEN ===")
    copiar(page["access_token"])
    print("Agora o TOKEN foi copiado (comeca com EAA). No GitHub: abra o segredo IG_ACCESS_TOKEN (lapis),")
    print("cole com Ctrl+V e salve. Nao copie mais nada antes disso.")


if __name__ == "__main__":
    main()
