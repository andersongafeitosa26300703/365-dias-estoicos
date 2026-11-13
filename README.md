# 365 Dias Estoicos

Posta uma citação estoica por dia no Instagram, sozinho, às 5h (Brasília).

## Como funciona
1. `data/calendar.json` tem as 365 citações, reflexões e hashtags.
2. Todo dia o GitHub Actions roda `scripts/post_daily.py`, que calcula o dia a partir de `config.json` (`start_date`), gera a imagem (`render.py`) e publica pela API oficial do Instagram.
3. `data/posted.json` registra o que já foi publicado, para nunca postar duas vezes o mesmo dia.

## Configuração única

### A. Instagram
1. Crie a conta **@365diasestoicos** e mude para **Conta profissional** (Criador de conteúdo): Configurações > Tipo de conta e ferramentas.
2. Crie uma **Página do Facebook** (pode ser só com o nome do perfil).
3. Vincule: Instagram > Editar perfil > Página > conectar a Página.

### B. App na Meta
1. Entre em <https://developers.facebook.com>, crie um app do tipo **Empresa (Business)**.
2. Adicione o produto **Instagram** (Instagram Graph API / "API do Instagram com login do Facebook").
3. Em **Graph API Explorer**, gere um token de usuário com as permissões `instagram_basic`, `instagram_content_publish`, `pages_show_list`, `pages_read_engagement`, `business_management`.
4. Troque por um token de longa duração e depois obtenha o **token da Página** (esse não expira). Anote também o **ID da conta do Instagram** (`GET /{page-id}?fields=instagram_business_account`).

### C. GitHub
1. Crie um repositório **público** (o Instagram precisa baixar a imagem por uma URL pública) e envie esta pasta.
2. Em Settings > Secrets and variables > Actions, crie:
   - `IG_USER_ID`: ID da conta do Instagram
   - `IG_ACCESS_TOKEN`: token da Página
3. Ajuste `start_date` em `config.json` para o dia do primeiro post (dia 1).
4. Teste: aba Actions > "Post diario" > Run workflow (campo `day` = 1).

## Comandos locais
```
python scripts/post_daily.py preview --day 10   # mostra a legenda
python scripts/post_daily.py prepare --day 10   # gera posts/dia-010.jpg
```

## Reels (opcional, desligado por padrao)
Com `"reels": true` em `config.json`, cada post do dia gera tambem um Reel (MP4 vertical, sem som, de 7 a 15 s) com a mesma
citacao: o cabecalho, a citacao, o autor e o "No trabalho" entram um a um. O fluxo e:
1. `prepare` grava `reels/dia-NNN.mp4` (e `dia-NNN.json` com a duracao e o quadro da capa) junto com a imagem do dia.
2. `publish-reel` roda depois do feed e do Story, com a mesma legenda, e registra `reel_media_id` em `data/posted.json`.
3. O passo do Reel usa `continue-on-error`: se falhar, o post do dia ja saiu e nada e desfeito.

Para testar antes de ligar de vez: ligue `reels`, rode o workflow manualmente (Run workflow, campo `day` do dia ja publicado
nao reposta o feed) e confira o Reel no perfil. Teste local: `python scripts/reel.py 10 saida.mp4` (precisa de ffmpeg).
Som: cada Reel leva um som ambiente suave (chuva, mata ou um fundo calmo), em rodizio por dia, com entrada e saida graduais.
Os tres sons sao sinteticos, gerados por `scripts/sons.py` (precisa de numpy e ffmpeg) e guardados em `assets/sons/`, entao nao ha
direitos autorais a conferir. Para fixar um som, use `"som": "chuva"`, `"mata"` ou `"calmo"` em `config.json`; para deixar sem
som, `"som": "nenhum"`. O padrao e `"rodizio"`. Musica da biblioteca do Instagram so pode ser adicionada pelo app.
Cada MP4 pesa algumas centenas de KB e fica no repositorio, porque o Instagram baixa o video por URL publica.

## Observações
- O agendador do GitHub pode atrasar de alguns minutos até ~30 min em horários de pico. Se precisar de hora exata, dá para trocar por outro agendador.
- Se uma execução falhar, o GitHub envia e-mail. Para reenviar um dia: Run workflow com o campo `day`.
- Fonte: EB Garamond (licença OFL, ver `fonts/OFL.txt`).
