# 365 Dias Estoicos

Posta uma citação estoica por dia no Instagram, sozinho, às 6h30 (Brasília).

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

## Observações
- O agendador do GitHub pode atrasar de alguns minutos até ~30 min em horários de pico. Se precisar de hora exata, dá para trocar por outro agendador.
- Se uma execução falhar, o GitHub envia e-mail. Para reenviar um dia: Run workflow com o campo `day`.
- Fonte: EB Garamond (licença OFL, ver `fonts/OFL.txt`).
