# Vigia na VPS (aviso e disparo fora do GitHub)

O agendador do GitHub Actions pode atrasar ou perder disparos. Este vigia roda na sua VPS, **independente do GitHub
e do seu notebook**, e faz duas coisas:

1. **Se o post do dia nao saiu**, dispara o workflow pela API do GitHub (precisa de um token restrito, opcional).
2. **Se continuar sem sair**, avisa no seu celular (app gratuito **ntfy**, sem conta e sem senha).

## Horarios (fuso de Brasilia)
| Hora | O que acontece |
|---|---|
| 05:00 | O GitHub publica (e reservas 05:20, 05:50, 06:30) |
| 05:15 | Vigia confere. Se nao saiu: dispara o workflow e te avisa que disparou |
| 05:45 | Vigia confere de novo. Se ainda nao saiu: **alerta urgente no celular** |
| 06:30 | Ultima conferencia. Se ainda nao saiu: alerta urgente de novo |

## Instalacao (uma vez, ~10 minutos)

### 1. No celular
Instale o app **ntfy** (Android/iOS) e assine um topico com um nome longo e dificil de adivinhar, por exemplo
`365dias-anderson-7k2x9q4m`. Quem souber o nome do topico consegue ler os avisos, entao nao use algo obvio.

### 2. (Opcional, recomendado) Token do GitHub para o vigia poder disparar o workflow
GitHub > Settings > Developer settings > **Personal access tokens > Fine-grained tokens > Generate new token**
- Repository access: **Only select repositories** > `365-dias-estoicos`
- Permissions: **Actions: Read and write** (e nada mais)
- Validade: 1 ano. Copie o token (comeca com `github_pat_`).

Sem esse token o vigia **so avisa**, nao dispara.

### 3. Na VPS (SSH)
```bash
sudo mkdir -p /opt/365dias
sudo curl -fsSL https://raw.githubusercontent.com/andersongafeitosa26300703/365-dias-estoicos/main/ops/vps/watch.py -o /opt/365dias/watch.py
sudo chmod +x /opt/365dias/watch.py
python3 --version   # precisa ser 3.9 ou mais novo
```
Crie o arquivo de configuracao (so root le):
```bash
sudo tee /etc/365dias.env >/dev/null <<'EOF'
NTFY_TOPIC=365dias-anderson-7k2x9q4m
GH_TOKEN=github_pat_COLE_AQUI_O_TOKEN
EOF
sudo chmod 600 /etc/365dias.env
```
(Troque o topico pelo que voce assinou no celular. Se nao for usar o token, deixe so a linha do `NTFY_TOPIC`.)

### 4. Teste (nao dispara nada de verdade)
```bash
sudo DRY_RUN=1 DAY=400 python3 /opt/365dias/watch.py        # dia fora do intervalo: so confirma que roda
sudo DRY_RUN=1 python3 /opt/365dias/watch.py                # confere o dia de hoje
sudo NTFY_TOPIC=SEU_TOPICO DAY=300 python3 /opt/365dias/watch.py   # deve chegar um alerta no celular
```
O terceiro comando simula um dia nao publicado e **deve fazer o celular tocar**. Se tocar, o canal funciona.

### 5. Agendar (cron da VPS)
```bash
sudo tee /etc/cron.d/365dias >/dev/null <<'EOF'
CRON_TZ=America/Sao_Paulo
15 5 * * * root /usr/bin/python3 /opt/365dias/watch.py >> /var/log/365dias.log 2>&1
45 5 * * * root /usr/bin/python3 /opt/365dias/watch.py >> /var/log/365dias.log 2>&1
30 6 * * * root /usr/bin/python3 /opt/365dias/watch.py >> /var/log/365dias.log 2>&1
EOF
```
Conferir depois: `tail -n 20 /var/log/365dias.log`.

## Se quiser um aviso diario de "deu certo"
Acrescente `NOTIFY_OK=1` ao `/etc/365dias.env`. Ele manda uma notificacao discreta quando o post do dia sai.

## Observacoes
- O vigia so le dados **publicos** do repositorio (config.json e posted.json); o unico segredo na VPS e o token opcional.
- Para trocar o canal por Telegram ou e-mail, basta adaptar a funcao `notify()` em `watch.py`.
