# CLAUDE.md — Plataforma de estudos ENEM (nome provisório: **Rumo1000**)

Este arquivo orienta o Claude Code. Leia-o inteiro antes de qualquer tarefa e consulte os documentos em `docs/` conforme indicado.

## O que é o projeto

Plataforma web para estudantes que se preparam para o ENEM, com três módulos:

1. **Correção de redações**: o aluno envia a foto da folha manuscrita. O sistema transcreve, o aluno revisa a transcrição e a IA corrige nas 5 competências do ENEM (0–200 cada, total 0–1000), com feedback detalhado.
2. **Banco de questões**: questões oficiais do ENEM organizadas por área do conhecimento, disciplina e tópico, com resolução, estatísticas de acerto e favoritos.
3. **Cronograma de estudos**: grade semanal (segunda a domingo × horários) em que o aluno monta blocos de estudo por matéria, com lembretes por e-mail.

O banco de questões também tem **questões de concursos públicos**, importadas pelo admin a partir do PDF da prova e do gabarito (área `CP`, itens de múltipla escolha e Certo/Errado).

Estado: as Fases 0 a 6 do `docs/06-roadmap.md` estão implementadas. Sem chave de IA configurada, o app usa o provedor simulado (`fake`).

## Stack (decidida)

| Camada | Tecnologia |
|---|---|
| Banco | PostgreSQL 16 |
| Backend | Python 3.12, FastAPI, SQLAlchemy 2.x (async) + asyncpg, Alembic, Pydantic v2. Dependências com **uv** |
| Worker | Processo Python separado, fila em tabela Postgres (`jobs`) com `FOR UPDATE SKIP LOCKED` (sem Redis) |
| IA | Anthropic (`anthropic`), OpenAI (`openai`) e Google (`google-genai`), escolhidos por tarefa no painel admin. Saída sempre estruturada (modelo Pydantic) |
| E-mail | Resend (SDK `resend`); em dev, driver `console` |
| Imagens e PDF | OpenCV + Pillow (fotos das redações); pypdfium2 (provas de concurso) |
| Storage | Disco local (dev e produção), em volume Docker, por trás da interface `Storage`. Acesso só por URL assinada (HMAC) |
| Frontend | Next.js (App Router) + TypeScript + Tailwind, dependências com **npm**, `output: "standalone"` |
| Infra local | Docker Compose (postgres, backend, worker, frontend) |
| Produção | **VPS própria**: `docker-compose.prod.yml` com Caddy (HTTPS automático), Postgres, backend, worker, frontend e backup diário |

### Restrições de hospedagem

- Tudo roda na VPS do projeto. **Não usar** Vercel, Cloudflare R2/S3, Postgres gerenciado nem outros serviços externos.
- Os únicos serviços externos permitidos são as **APIs de IA** (Anthropic, OpenAI, Google) e o **Resend**.
- O projeto **não usa git** por enquanto: não rode comandos git nem crie `.git`.

## Documentos

- `docs/01-visao-produto.md`: funcionalidades, fluxos e escopo do MVP
- `docs/02-arquitetura.md`: arquitetura, pastas, worker, storage, auth, e-mails (onde ele citar Vercel ou R2/S3, vale a seção "Restrições de hospedagem" acima)
- `docs/03-banco-de-dados.md` + `db/schema.sql`: modelo de dados (o SQL é a **referência**; a fonte da verdade em código são os models + migrations Alembic)
- `docs/04-api.md`: endpoints REST
- `docs/05-correcao-redacao.md`: pipeline de IA, prompts, grade das competências, saída estruturada e calibração
- `docs/06-roadmap.md`: fases de implementação com critérios de aceite e o que ficou pendente
- `deploy/README.md`: deploy na VPS, backup e restauração
- `docs/a_redacao_no_enem_2025_cartilha_do_participante.pdf`: Cartilha do INEP, fonte da rubrica em `app/ai/prompts/rubrica.md`

## Convenções

- Código, nomes de tabelas e colunas em **inglês**. Textos de interface, prompts da IA e mensagens ao usuário em **português do Brasil**.
- Backend organizado por módulo de domínio (`app/modules/<modulo>/` com `router.py`, `schemas.py`, `models.py`, `service.py`). Routers finos e regra de negócio no `service`.
- Erros da API sempre no formato `{"error": {"code", "message", "details"}}` (`app/core/errors.py`), com mensagem em pt-BR.
- IDs `uuid` para entidades do usuário. IDs inteiros para catálogos (áreas, disciplinas, questões).
- Datas sempre `timestamptz` em UTC no banco. A conversão para o fuso do usuário (`users.timezone`) acontece na borda.
- Toda chamada de IA passa por `app/ai/client.py` (`get_ai_client().parse(AIRequest)`), que registra uso e custo em `ai_usage`. Nunca chame um SDK direto de um módulo. O pedido é neutro (`TextPart`, `ImagePart`, `PdfPart`) e cada provedor tem um adaptador em `app/ai/providers/`.
- Provedor, modelo e esforço vêm de `resolve_task(session, "<tarefa>")` (`app/ai/config.py`): primeiro o painel (`app_settings.ai_tasks`), depois o `.env`. Nunca hardcoded.
- Chaves de API salvas pelo painel ficam criptografadas (`ai_credentials`, Fernet com `SETTINGS_ENCRYPTION_KEY`) e nunca saem em nenhuma resposta da API.
- O painel admin mostra **só números agregados**: nenhuma rota `/admin/*` devolve nome, e-mail, texto de redação ou respostas de aluno (o teste `tests/test_system.py` varre as rotas). A fila mostra os jobs sem payload.
- Configurações editáveis pelo painel ficam em `app_settings` (`app/modules/system/settings.py`): módulos ligados (`require_feature`), limites e orçamento de IA, tarefas de IA e preços.
- Prompts ficam em `app/ai/prompts/*.md` com versão no cabeçalho (`prompt_version`). Toda correção grava a versão usada.
- Trabalho assíncrono (IA, e-mails, limpeza) vai para a fila com `app/jobs/queue.enqueue`, na mesma transação de quem chama. Handlers registrados com `@job_handler`.
- Testes com `pytest` + `httpx.AsyncClient`. Chamadas aos provedores de IA e ao Resend são **mockadas** nos testes.
- Nada de segredos no repositório. Use `.env` (com `.env.example` versionado); em produção, `.env.prod` (modelo em `.env.prod.example`).

## Variáveis de ambiente

Lista completa e comentada em `.env.example`. As principais:

```
DATABASE_URL=postgresql+asyncpg://app:app@postgres:5432/rumo1000
TEST_DATABASE_URL=postgresql+asyncpg://app:app@postgres:5432/rumo1000_test
JWT_SECRET=troque-isto
APP_URL=http://localhost:3000        # no dev local deste projeto: 3001 (FRONTEND_PORT=3001)
API_URL=http://localhost:8000
COOKIE_SECURE=false                  # true em produção

AI_DRIVER=fake                       # padrão quando o painel não configurou: fake | anthropic
ANTHROPIC_API_KEY=                   # reservas: as chaves do painel têm prioridade
ANTHROPIC_MODEL_TRANSCRIPTION=claude-sonnet-5-5
ANTHROPIC_MODEL_GRADING=claude-sonnet-5-5
OPENAI_API_KEY=
GOOGLE_API_KEY=
SETTINGS_ENCRYPTION_KEY=             # Fernet; criptografa as chaves salvas pelo painel

EMAIL_DRIVER=console                 # console | resend
RESEND_API_KEY=
EMAIL_FROM="Rumo1000 <nao-responda@seudominio.com.br>"

STORAGE_DRIVER=local
STORAGE_LOCAL_PATH=/data/storage

SEED_ADMIN_EMAIL=admin@example.com
SEED_ADMIN_PASSWORD=troque-esta-senha
```

## Comandos

```
docker compose up -d                                   # sobe tudo (front em :3001 neste ambiente, API em :8000)
docker compose exec backend alembic upgrade head
docker compose exec backend pytest
docker compose exec backend ruff check .
docker compose exec backend python -m scripts.seed     # temas oficiais, tópicos e admin
docker compose exec backend python -m scripts.import_questions --year 2023 [--microdados data/inep/ITENS_PROVA_2023.csv]
docker compose exec backend python -m scripts.eval_grading --dataset data/essay-br --n 5 [--yes] [--provider openai --model <id>]
docker compose exec backend python -m scripts.enqueue system.ping '{}'
docker compose restart worker                          # o worker não recarrega sozinho após mudar código
docker compose exec frontend npm run lint
docker compose exec frontend npx tsc --noEmit
```

- `eval_grading` com um provedor real gasta créditos: exige `--yes`. Comece com `--n 5`. Calibre cada modelo antes de usá-lo na correção em produção.
- Produção: veja `deploy/README.md` (`docker compose -f docker-compose.prod.yml --env-file .env.prod ...`).

## Regras importantes de domínio

- Na correção de redação, a **transcrição deve ser literal**, preservando os erros do aluno. Ela nunca pode corrigir ortografia, senão a Competência 1 fica inflada. Veja `docs/05`.
- A correção só roda depois que o aluno **confirma** a transcrição revisada.
- Notas por competência em cada execução: apenas `0, 40, 80, 120, 160, 200`.
- Redação anulada (motivo de nota zero) zera todas as competências.
- O gabarito de uma questão nunca é enviado ao aluno antes de ele responder (exceto no modo lista, ao finalizar).
- Blocos do cronograma não podem se sobrepor no mesmo dia (encostar é permitido) e não cruzam a meia-noite.
- Questões de concurso importadas ficam com `is_published = false` até o admin publicar a prova; só então aparecem para os alunos. Itens Certo/Errado têm `format = true_false` e gabarito `C` ou `E`.
- Questões ENEM e de concurso ficam na mesma tabela; o filtro `track` (`enem` | `concurso`) separa as duas trilhas, e cada uma tem seu interruptor no painel.

## Decisões que divergem dos docs originais

- **Saída estruturada em vez de `tool_choice` forçado** (`docs/05`): o `claude-sonnet-5-5` recusa `tool_choice` forçado. Usamos a saída estruturada de cada provedor com modelo Pydantic.
- **IA multi-provedor** (Fase 6): `docs/02` e `docs/05` falam só da Anthropic; hoje o provedor é escolhido por tarefa no painel.
- **Sem campo `analise`** no JSON da correção: o raciocínio fica no thinking do modelo; a justificativa ao aluno continua.
- **Área das questões** vem da posição no caderno, não do campo `discipline` do enem.dev (que tem erros).
- O cadastro já devolve a sessão logada; menores de 18 exigem `guardian_consent`.
