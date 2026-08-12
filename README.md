# finance-bot

Controle de gastos por conversa. Você escreve _"gastei 45 no mercado"_ e ele
entende, categoriza, guarda e responde com o acumulado do mês.

Roda em dois modos com a **mesma lógica**:

- **CLI** (`python -m app.cli`) — funciona agora, só precisa da chave da Anthropic.
- **WhatsApp** (`uvicorn app.server:app`) — precisa da conta Meta Business configurada.

---

## Começando (2 minutos, de graça)

O ambiente virtual e as dependências já estão instalados em `.venv/`.

```powershell
Copy-Item .env.example .env          # se ainda não existir
.\.venv\Scripts\python.exe -m app.cli
```

Só isso. **Não precisa de chave de API** — sem chave, o bot usa o interpretador
por regras (`app/parser_local.py`), que custa zero e funciona offline.

### Os dois interpretadores

A variável `INTERPRETADOR` no `.env` escolhe quem lê as mensagens. Os dois
devolvem o mesmo formato, então o resto do app não muda:

| | `local` (regras) | `claude` (LLM) |
|---|---|---|
| Custo | zero | ~US$ 0,004–0,018 por mensagem |
| Internet | não precisa | precisa |
| Latência | instantâneo | 1–3 s |
| Entende | frases diretas: `gastei 45 no mercado`, `almoço 32 e uber 18`, `quanto gastei com transporte?` | praticamente qualquer forma de escrever |
| Erra em | frases criativas, gírias fora da lista, contexto implícito | pouca coisa |

`auto` (padrão) usa o Claude se houver `ANTHROPIC_API_KEY`, senão o local. Ou
seja: **funciona hoje de graça e vira LLM no dia que você puser crédito**, sem
tocar em código.

Para comparar os dois lado a lado, troque `INTERPRETADOR=local` / `claude` e
rode o CLI com as mesmas frases.

Exemplo de sessão:

```
você › gastei 45,90 no mercado e 32 no almoço
  bot │ 💸 R$ 45,90 · Mercado — compra do mercado (hoje)
  bot │ 💸 R$ 32,00 · Alimentação — almoço (hoje)
      │
  bot │ _Total do mês: R$ 77,90_

você › quanto gastei com comida esse mês?
  bot │ *Alimentação* este mês: R$ 32,00

você › resumo do mês
  bot │ *Gastos este mês: R$ 77,90*
      │
  bot │ ██████░░░░ R$ 45,90
  bot │     Mercado · 1x · 59%
  bot │ ████░░░░░░ R$ 32,00
  bot │     Alimentação · 1x · 41%
```

### Testes

Rodam sem chave de API e sem internet:

```powershell
.\.venv\Scripts\python.exe -m tests.test_smoke     # banco, moeda, períodos, respostas
.\.venv\Scripts\python.exe -m tests.test_parser    # interpretador local (regras)
.\.venv\Scripts\python.exe -m tests.test_webhook   # webhook ponta a ponta
```

---

## Como está montado

```
mensagem  ──►  ai.py       Claude classifica a intenção e extrai os campos
                           (sempre via tool use — nunca texto livre)
               │
               ▼
               brain.py    aplica no banco e REDIGE a resposta
               │           a partir de dados reais
               ▼
               db.py       SQLite · valores em centavos (int), nunca float
```

**O modelo não escreve números.** Ele só devolve `{valor: 45.9, categoria: "mercado", ...}`;
todos os totais e textos saem do `brain.py` lendo o banco. É o que impede o bot de
inventar um saldo.

| Arquivo | Responsabilidade |
|---|---|
| `app/ai.py` | Seletor de interpretador + ferramentas e chamada ao Claude |
| `app/parser_local.py` | Interpretador por regras (custo zero) |
| `app/brain.py` | Regras de negócio, períodos, textos de resposta |
| `app/db.py` | Esquema e consultas SQLite |
| `app/fmt.py` | Moeda em BRL, datas, mini-gráfico de barras |
| `app/whatsapp.py` | Cloud API + validação de assinatura HMAC |
| `app/server.py` | Webhook FastAPI |
| `app/cli.py` | Simulador local |

### Decisões que valem saber

- **Dinheiro é `INTEGER` em centavos.** Float acumula erro e some com centavos
  ao longo de centenas de lançamentos.
- **Idempotência de webhook.** A Meta reentrega quando não recebe `200` em ~20s.
  A tabela `mensagens_processadas` impede que uma reentrega lance o mesmo gasto
  duas vezes. Está coberto por teste.
- **Assinatura HMAC obrigatória.** Sem isso, quem descobrisse a URL do webhook
  conseguiria injetar lançamentos na conta de outra pessoa.
- **`apaga o último` é LIFO por ordem de inserção**, não por data do gasto — é o
  que "último" significa para quem acabou de digitar errado.
- **Vários lançamentos numa mensagem só** funcionam: o modelo emite uma chamada
  de ferramenta por lançamento.

---

## App no celular (PWA) — `pwa/`

Uma segunda interface, **independente do bot**: roda no Android e no iPhone,
instala na tela inicial com ícone, funciona offline e **não usa servidor
nenhum**. Os dados ficam no próprio aparelho (`localStorage`).

```powershell
cd pwa
..\.venv\Scripts\python.exe -m http.server 8321
# abra http://127.0.0.1:8321 no navegador
```

`pwa/teste.html` roda 70 testes do interpretador direto no navegador — abra
para conferir depois de mexer nas regras.

### Publicar de graça (GitHub Pages)

PWA exige HTTPS (é o que libera o service worker). Você **não precisa comprar
domínio** — o host te dá um subdomínio com certificado:

1. Crie um repositório público e suba a pasta `pwa/`.
2. *Settings → Pages → Source: Deploy from a branch*, escolha `main` e a pasta.
3. Em ~1 minuto o app está em `https://SEU-USUARIO.github.io/SEU-REPO/`.

Cloudflare Pages, Netlify e Vercel funcionam igual, com o mesmo custo: zero.

### Instalar no celular

- **Android/Chrome:** aparece um botão ⬇︎ no cabeçalho, ou *menu → Instalar app*.
- **iPhone/Safari:** *Compartilhar → Adicionar à Tela de Início*. O app avisa
  isso sozinho ao detectar iOS. (Não funciona pelo Chrome no iPhone — tem que
  ser o Safari.)

### O preço de não ter servidor

| | |
|---|---|
| ✅ | Custo zero, offline, privado — nada sai do aparelho |
| ⚠️ | Os dados vivem **só naquele aparelho**. Não sincroniza com o bot do WhatsApp nem com outro celular |
| ⚠️ | Limpar os dados do navegador apaga tudo — use *menu → Exportar* de vez em quando |

O menu (⋯) tem exportar/importar JSON, que é o backup manual e também o jeito
de levar os dados para outro aparelho.

### As regras são as mesmas do bot

`pwa/parser.js` é um porte fiel de `app/parser_local.py` — mesmas categorias,
mesmos gatilhos, mesmo tratamento de datas e valores. Mexeu num, mexa no outro
e rode os dois conjuntos de teste.

---

## Ligando no WhatsApp

O modo CLI não precisa de nada disso. Faça quando quiser sair do seu terminal.

**1. Conta e app na Meta**
Em [developers.facebook.com](https://developers.facebook.com) crie um app do tipo
_Business_ e adicione o produto **WhatsApp**. Em _API Setup_ você recebe um número
de teste, o `PHONE_NUMBER_ID` e um token temporário (24h) — suficiente para testar.

**2. Preencha o `.env`**
`WHATSAPP_PHONE_NUMBER_ID`, `WHATSAPP_ACCESS_TOKEN`, `WHATSAPP_APP_SECRET`
(em _Configurações do app > Básico_) e um `WHATSAPP_VERIFY_TOKEN` que você inventa.

**3. Exponha o servidor**
A Meta precisa de uma URL HTTPS pública. Em desenvolvimento:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.server:app --port 8000
# noutro terminal:
ngrok http 8000
```

**4. Cadastre o webhook**
Em _WhatsApp > Configuration_, informe `https://SEU-DOMINIO/webhook` e o mesmo
`verify_token` do `.env`. Assine o campo **`messages`**. A Meta faz um `GET` de
verificação na hora — se o token bater, valida na hora.

**5. Mande uma mensagem** para o número de teste.

> ⚠️ **Confira a versão da Graph API.** O `.env.example` traz `v23.0`, mas a Meta
> descontinua versões depois de ~2 anos. Veja a atual no
> [changelog](https://developers.facebook.com/docs/graph-api/changelog) e ajuste
> `GRAPH_API_VERSION` — uma versão morta falha com erro pouco óbvio.

### Para produção

- Token permanente via _System User_ (o de _API Setup_ expira em 24h).
- Verificação do negócio na Meta para sair do número de teste.
- Migre `DB_PATH` para Postgres se for ter mais de um usuário sério — o SQLite
  atual segura bem um uso pessoal, mas não escrita concorrente pesada.
- Deploy: Railway, Fly.io ou Render rodam isso direto com `uvicorn app.server:app --host 0.0.0.0 --port $PORT`.

---

## Custos

**Claude** — o `.env.example` usa `claude-opus-5`, que é o modelo mais capaz.
Para lançamentos simples, `claude-haiku-4-5` custa uma fração e a diferença é
pequena nesta tarefa; troque `ANTHROPIC_MODEL` e compare no CLI. O código já
ajusta os parâmetros automaticamente conforme o modelo escolhido.

**WhatsApp** — conversas iniciadas pelo usuário (janela de 24h) são gratuitas.
Como aqui é sempre você que fala primeiro, quase tudo cai na faixa sem custo.
Só alertas proativos fora da janela são cobrados.

---

## O que não está aqui (ainda)

- **Conexão com bancos.** Fora do escopo desta versão. Quando quiser, o caminho é
  [Pluggy](https://pluggy.ai) ou [Belvo](https://belvo.com) — ambos já são
  participantes regulados do Open Finance Brasil, então você não precisa ser.
- **Áudio e imagem.** O `whatsapp.py` ignora mensagens que não são texto. Comprovante
  Pix por foto é um próximo passo natural — o Claude já lê imagem, então é
  basicamente baixar a mídia da Meta e mandar junto no `ai.py`.
- **Orçamento por categoria** com alerta ao estourar.
- **Exportar CSV / dashboard web.**

## LGPD

Dado financeiro é dado sensível. Se isso for além de uso pessoal, você precisa de
política de privacidade, criptografia em repouso e um fluxo de exclusão de dados.
O `.gitignore` já bloqueia `.env` e `*.db` — não versione nenhum dos dois.
