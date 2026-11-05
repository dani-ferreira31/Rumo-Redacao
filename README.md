# Rumo1000

Plataforma de estudos para o ENEM com correção de redações por IA, banco de questões oficiais e cronograma de estudos.

> **Uso comercial proibido.** O código é público para estudo e portfólio, sob a [PolyForm Noncommercial 1.0.0](LICENSE). Para uso comercial, fale com o autor.

## Funcionalidades

- **Correção de redações:** o aluno envia uma foto da folha manuscrita, a IA transcreve, o aluno revisa o texto e a IA corrige nas 5 competências do ENEM (0 a 1000), com feedback detalhado.
- **Banco de questões:** questões oficiais do ENEM de 2009 a 2023, organizadas por área, disciplina e tópico, com estatísticas de acerto e favoritos. Também tem questões de concursos públicos, importadas a partir do PDF da prova.
- **Cronograma de estudos:** grade semanal com blocos por matéria e lembretes por e-mail que respeitam o fuso horário do aluno.
- **Provas de professor:** montagem de provas com questões do banco.
- **Assinatura e doações** pelo Mercado Pago.
- **Painel admin:** provedor e modelo de IA por tarefa, orçamento de IA e módulos ativos. O painel mostra só números agregados, sem dados pessoais dos alunos.

## Destaques técnicos

- **Pipeline de IA com vários provedores:** Anthropic, OpenAI e Google atrás de um adaptador único, com saída estruturada (Pydantic), registro de uso e custo, e prompts versionados.
- **Calibração da correção com notas humanas** (dataset Essay-BR), usando QWK, erro médio e matriz de confusão por competência.
- **Fila de jobs no próprio Postgres** com `FOR UPDATE SKIP LOCKED`, sem Redis.
- **Importador de questões** que cruza os dados abertos do enem.dev com os microdados do INEP (TRI e habilidades).
- **Segurança:** chaves de API criptografadas no banco (Fernet), arquivos acessíveis só por URL assinada (HMAC) e um teste que garante que nenhuma rota de admin expõe dados de aluno.
- **182 testes automatizados** (pytest), com os provedores de IA e de e-mail mockados.

## Stack

- **Linguagens:** Python, TypeScript, SQL
- **Backend:** FastAPI, SQLAlchemy 2 (async), Alembic, Pydantic v2, uv
- **Frontend:** Next.js 16, React 19, Tailwind CSS
- **Banco:** PostgreSQL 16
- **IA e imagem:** SDKs da Anthropic, OpenAI e Google GenAI; OpenCV, Pillow e pypdfium2
- **Infra:** Docker Compose, Caddy e Nginx Proxy Manager em VPS, com backup diário; e-mail pelo Resend

A documentação técnica completa está em `docs/`.

## Rodando em desenvolvimento

```bash
cp .env.example .env            # ajuste JWT_SECRET; troque as portas se 3000/5432/8000 estiverem ocupadas
docker compose up -d --build    # postgres, backend (:8000), worker e frontend (:3000)
docker compose exec backend alembic upgrade head
```

- App: http://localhost:3000. A API fica em `/api/v1`, repassada ao backend pelo rewrite do Next.
- Docs da API: http://localhost:8000/docs
- E-mails: com `EMAIL_DRIVER=console`, o worker só loga o e-mail (inclusive os links de verificação e de redefinição de senha), então use `docker compose logs -f worker` para ver. Com `EMAIL_DRIVER=resend` + `RESEND_API_KEY`, o envio é real (no modo de teste, use o destinatário `delivered@resend.dev`).

## Dados (fora do git, em `data/`)

```bash
# Questões do ENEM 2009–2023 (texto, imagens e gabarito), do projeto aberto enem.dev
git clone --depth 1 --filter=blob:none --sparse https://github.com/yunger7/enem-api.git data/enem-api
(cd data/enem-api && git sparse-checkout set public && rm -rf .git)
docker compose exec backend python -m scripts.import_questions $(for y in $(seq 2009 2023); do echo --year $y; done)

# Opcional: TRI e habilidade (H1–H30) dos microdados do INEP. Baixe o zip dos microdados
# do ENEM no site do INEP, extraia DADOS/ITENS_PROVA_<ano>.csv para data/inep/ e rode, um ano por vez:
docker compose exec backend python -m scripts.import_questions --year 2023 --microdados data/inep/ITENS_PROVA_2023.csv

# Redações com notas humanas para calibrar a correção (Essay-BR, licença MIT)
git clone --depth 1 https://github.com/rafaelanchieta/essay.git data/essay-br && rm -rf data/essay-br/.git

# Temas oficiais de redação, tópicos e admin de desenvolvimento
docker compose exec backend python -m scripts.seed
```

O importador cruza as duas fontes sozinho: para cada área, escolhe o caderno dos microdados cujo gabarito coincide com o do enem.dev. A área vem da **posição** da questão, porque o campo `discipline` do enem.dev tem erros.

## IA (correção de redações)

- O provedor (Anthropic, OpenAI ou Google), o modelo e o esforço de cada tarefa (transcrição, correção, importação de provas) são escolhidos em **Admin → Inteligência artificial**, sem reiniciar nada.
- As chaves de API também são cadastradas lá. Elas ficam criptografadas no banco com `SETTINGS_ENCRYPTION_KEY`, que precisa estar no `.env`. Gere uma com:
  `docker compose exec backend python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`
  Guarde essa chave junto com os backups: sem ela, as chaves salvas no painel não podem ser lidas (basta cadastrá-las de novo).
- Sem nada configurado no painel, vale o `.env`: `AI_DRIVER=fake` (padrão em dev) dá respostas simuladas, sem custo; `AI_DRIVER=anthropic` + `ANTHROPIC_API_KEY` usa a Anthropic.
- Antes de trocar o modelo de correção em produção, rode a calibração com ele: `python -m scripts.eval_grading --n 50 --yes --provider openai --model <id>`.
- Calibração com notas humanas: `docker compose exec -u "$(id -u):$(id -g)" backend python -m scripts.eval_grading --dataset data/essay-br --n 50 --yes`. Gera um relatório em `reports/`.

## Comandos úteis

```bash
docker compose exec backend pytest                    # banco rumo1000_test, transação revertida por teste
docker compose exec backend ruff check .
docker compose exec backend python -m scripts.enqueue system.ping '{}'
docker compose exec frontend npm run lint
docker compose exec frontend npm run typecheck
cd frontend && npm run gen:api                        # regenera lib/api-schema.d.ts (backend no ar)
```

Para adicionar dependências Python, edite `backend/pyproject.toml` e rode `docker compose run --rm --user "$(id -u):$(id -g)" -e UV_CACHE_DIR=/tmp/uv backend uv lock`. Depois faça `docker compose build backend worker`.

## Notas

- **Hospedagem:** VPS própria com Docker Compose, atrás do Cloudflare e do Nginx Proxy Manager (HTTPS e mesma origem para front e API). Os únicos serviços externos são o Resend e a Anthropic. O storage é em disco local (volume com backup diário). Guia: `deploy/README.md`.
- **Hot reload:** o backend recarrega sozinho. O **worker não**: depois de mudar código de jobs, rode `docker compose restart worker`. Se uma alteração do frontend não aparecer, rode `docker compose restart frontend`.
- **Dependências novas do frontend:** o `node_modules` do container fica num volume. Depois de `npm install`, recrie o volume com `docker compose rm -sf frontend && docker volume rm rumo1000_frontend_node_modules && docker compose up -d frontend`.
- **Produção:** veja `deploy/README.md`.

## Licença

[PolyForm Noncommercial 1.0.0](LICENSE): você pode ler, estudar, modificar e usar o código para fins **não comerciais**. Qualquer uso comercial depende de autorização por escrito do autor.

© 2026 Daniel Ferreira — 4B Sistemas
